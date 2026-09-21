"""
Pydantic v2 data models for dossier, entities, and kinship extraction.
Strict validation and schema generation for structured LLM outputs.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ContactInfo(BaseModel):
    """Контакты субъекта: телефоны, email, мессенджеры."""
    phone_numbers: List[str] = Field(
        default_factory=list,
        description="Список выявленных телефонных номеров в международном или локальном формате"
    )
    emails: List[str] = Field(
        default_factory=list,
        description="Список адресов электронной почты"
    )
    social_profiles: List[str] = Field(
        default_factory=list,
        description="Никнеймы, профили в мессенджерах (Telegram, WhatsApp) или социальных сетях"
    )

    @field_validator("phone_numbers", "emails", "social_profiles", mode="before")
    @classmethod
    def filter_empty_strings(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            return [str(item).strip() for item in v if item and str(item).strip()]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []


class Address(BaseModel):
    """Сведения об адресе: прописка, фактический, прошлые места проживания."""
    address_type: str = Field(
        default="фактический",
        description="Тип адреса: прописка / юридический / фактический / прежний / недвижимость"
    )
    full_address: str = Field(
        ...,
        description="Полный адрес объекта (страна, область, город, улица, дом, квартира)"
    )
    city: Optional[str] = Field(
        default=None,
        description="Город или населенный пункт"
    )
    region: Optional[str] = Field(
        default=None,
        description="Область / регион / штат"
    )


class Employment(BaseModel):
    """Место работы, служба, владение бизнесом или занятость."""
    organization: str = Field(
        ...,
        description="Наименование организации, компании или государственного органа"
    )
    bin: Optional[str] = Field(
        default=None,
        description="БИН или ИНН организации (при наличии)"
    )
    position: Optional[str] = Field(
        default=None,
        description="Должность, статус или роль в организации"
    )
    period: Optional[str] = Field(
        default=None,
        description="Период работы (например, '2018 - 2023' или 'с 2021 по настоящее время')"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Дополнительные детали: сфера деятельности, доли участия, статус увольнения"
    )


class RelativeRelation(BaseModel):
    """Родственные, семейные и аффилированные связи."""
    full_name: str = Field(
        ...,
        description="ФИО родственника, супруга(и) или аффилированного лица"
    )
    relation_type: str = Field(
        ...,
        description="Степень родства или тип связи: отец, мать, супруг(а), сын, дочь, брат, сестра, деловой партнер"
    )
    iin: Optional[str] = Field(
        default=None,
        description="ИИН или ИНН персоны (12 цифр для РК или 10/12 для РФ при наличии)"
    )
    birth_date: Optional[str] = Field(
        default=None,
        description="Дата рождения связанного лица (ГГГГ-ММ-ДД или год)"
    )
    shared_attributes: List[str] = Field(
        default_factory=list,
        description="Общие признаки связи: общий адрес, общий телефон, общее владение долями или имуществом"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Дополнительные комментарии аналитика по характеру связи"
    )

    @field_validator("shared_attributes", mode="before")
    @classmethod
    def clean_shared_attributes(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            return [str(item).strip() for item in v if item and str(item).strip()]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []


class SubjectProfile(BaseModel):
    """Анкетные данные основного субъекта проверки."""
    full_name: str = Field(
        ...,
        description="Полное имя субъекта (ФИО) в именительном падеже"
    )
    iin: Optional[str] = Field(
        default=None,
        description="ИИН / ИНН субъекта"
    )
    birth_date: Optional[str] = Field(
        default=None,
        description="Дата рождения (в формате ДД.ММ.ГГГГ или ГГГГ-ММ-ДД)"
    )
    birth_place: Optional[str] = Field(
        default=None,
        description="Место рождения"
    )
    citizenship: Optional[str] = Field(
        default="Республика Казахстан",
        description="Гражданство субъекта"
    )
    gender: Optional[str] = Field(
        default=None,
        description="Пол (мужской / женский)"
    )


class DossierReport(BaseModel):
    """Итоговое структурированное аналитическое досье."""
    subject: SubjectProfile = Field(
        ...,
        description="Анкета основного проверяемого лица"
    )
    contacts: ContactInfo = Field(
        default_factory=ContactInfo,
        description="Контакты (телефоны, почта, социальные сети)"
    )
    addresses: List[Address] = Field(
        default_factory=list,
        description="Список всех выявленных адресов"
    )
    employment_history: List[Employment] = Field(
        default_factory=list,
        description="Места работы, должности и история занятости"
    )
    relatives_and_affiliates: List[RelativeRelation] = Field(
        default_factory=list,
        description="Родственники, члены семьи и аффилированные лица"
    )
    executive_summary: str = Field(
        default="Аналитическое резюме формируется на основе предоставленных документов.",
        description="Сводные выводы аналитика: ключевые факты, риски, совпадения признаков и заключение"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Технические метаданные обработки (файлы источников, модель, дата генерации)"
    )

    @classmethod
    def get_json_schema(cls) -> Dict[str, Any]:
        """Возвращает JSON Schema для передачи в Ollama/vLLM structured output."""
        return cls.model_json_schema()
