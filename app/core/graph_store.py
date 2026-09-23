import logging
from typing import Optional, Dict, Any
from neo4j import GraphDatabase
from app.config import settings
from app.core.schemas import DossierReport

logger = logging.getLogger(__name__)

class GraphKnowledgeBase:
    """
    Класс для работы с графовой базой данных Neo4j.
    Позволяет сохранять досье в виде графа и извлекать исторические связи (Cross-Referencing).
    """

    def __init__(self):
        self.uri = settings.NEO4J_URI
        self.user = settings.NEO4J_USER
        self.password = settings.NEO4J_PASSWORD
        self.driver = None
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            logger.info("Connected to Neo4j successfully.")
            self._init_schema()
        except Exception as e:
            logger.error("Failed to connect to Neo4j: %s", e)

    def _init_schema(self):
        """Создание индексов и констрейнтов для быстрого поиска."""
        if not self.driver:
            return
        try:
            with self.driver.session() as session:
                session.run("CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.full_name IS UNIQUE")
                session.run("CREATE CONSTRAINT org_name IF NOT EXISTS FOR (o:Organization) REQUIRE o.name IS UNIQUE")
                session.run("CREATE CONSTRAINT address_val IF NOT EXISTS FOR (a:Address) REQUIRE a.full_address IS UNIQUE")
        except Exception as e:
            logger.error("Failed to initialize Neo4j schema: %s", e)

    def close(self):
        if self.driver:
            self.driver.close()

    def merge_dossier(self, dossier: DossierReport):
        """Сохранение/обновление досье в графе Neo4j."""
        if not self.driver:
            logger.warning("Neo4j driver not initialized, skipping graph merge.")
            return

        subject = dossier.subject
        if not subject.full_name:
            return

        with self.driver.session() as session:
            # 1. Merge Main Subject
            session.run('''
                MERGE (p:Person {full_name: $name})
                SET p.iin = coalesce($iin, p.iin), p.birth_date = coalesce($birth_date, p.birth_date)
            ''', name=subject.full_name, iin=subject.iin, birth_date=subject.birth_date)

            # 2. Merge Addresses
            for addr in dossier.addresses:
                session.run('''
                    MERGE (p:Person {full_name: $name})
                    MERGE (a:Address {full_address: $addr_val})
                    MERGE (p)-[r:LIVES_AT]->(a)
                    SET r.type = $addr_type
                ''', name=subject.full_name, addr_val=addr.full_address, addr_type=addr.address_type)

            # 3. Merge Employment
            for emp in dossier.employment_history:
                session.run('''
                    MERGE (p:Person {full_name: $name})
                    MERGE (o:Organization {name: $org_name})
                    MERGE (p)-[r:WORKS_AT]->(o)
                    SET r.position = coalesce($position, r.position), r.period = coalesce($period, r.period), o.bin = coalesce($bin, o.bin)
                ''', name=subject.full_name, org_name=emp.organization, 
                     position=emp.position, period=emp.period, bin=emp.bin)

            # 4. Merge Relatives
            for rel in dossier.relatives_and_affiliates:
                session.run('''
                    MERGE (p1:Person {full_name: $subj_name})
                    MERGE (p2:Person {full_name: $rel_name})
                    SET p2.iin = coalesce($rel_iin, p2.iin), p2.birth_date = coalesce($rel_birth_date, p2.birth_date)
                    MERGE (p1)-[r:RELATED_TO]-(p2)
                    SET r.relation_type = coalesce($rel_type, r.relation_type)
                ''', subj_name=subject.full_name, rel_name=rel.full_name,
                     rel_iin=rel.iin, rel_birth_date=rel.birth_date, rel_type=rel.relation_type)

            logger.info("Successfully merged dossier into Neo4j graph for: %s", subject.full_name)

    def get_historical_context(self, full_name: str, iin: Optional[str] = None) -> str:
        """
        Ищет субъекта в графе по имени или ИИН и возвращает краткую историческую справку, 
        которую можно добавить в промпт для LLM.
        """
        if not self.driver:
            return ""

        context_lines = []
        with self.driver.session() as session:
            # Поиск по ФИО
            res = session.run('''
                MATCH (p:Person {full_name: $name})
                OPTIONAL MATCH (p)-[r:WORKS_AT]->(o:Organization)
                OPTIONAL MATCH (p)-[r2:LIVES_AT]->(a:Address)
                OPTIONAL MATCH (p)-[r3:RELATED_TO]-(p2:Person)
                RETURN 
                    collect(DISTINCT {org: o.name, pos: r.position}) as employment,
                    collect(DISTINCT a.full_address) as addresses,
                    collect(DISTINCT {rel: p2.full_name, type: r3.relation_type}) as relatives
            ''', name=full_name)

            record = res.single()
            if not record:
                return ""

            employment = [e for e in record["employment"] if e.get("org")]
            addresses = [a for a in record["addresses"] if a]
            relatives = [r for r in record["relatives"] if r.get("rel")]

            if not employment and not addresses and not relatives:
                return ""

            context_lines.append(f"--- ИСТОРИЧЕСКИЕ ДАННЫЕ ИЗ БАЗЫ (NEO4J) ДЛЯ {full_name} ---")
            
            if relatives:
                context_lines.append("Известные родственники/связи:")
                for r in relatives:
                    context_lines.append(f" - {r['rel']} ({r['type']})")
                    
            if employment:
                context_lines.append("Известные места работы:")
                for e in employment:
                    context_lines.append(f" - {e['org']} (Должность: {e['pos']})")
                    
            if addresses:
                context_lines.append("Известные адреса:")
                for a in addresses:
                    context_lines.append(f" - {a}")
                    
        return "\n".join(context_lines)
