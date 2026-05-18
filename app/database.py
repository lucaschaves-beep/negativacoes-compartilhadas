from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, Text, Boolean, Float, Date, DateTime, ARRAY, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.pool import NullPool
from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime, timezone
from app.config import get_settings

settings = get_settings()

# NullPool = sem conexões persistentes (obrigatório em serverless/Vercel)
# SSL obrigatório para Supabase em produção
db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
engine = create_async_engine(
    db_url,
    echo=False,
    poolclass=NullPool,
    connect_args={"ssl": "require"},
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class GrupoEmpresarial(Base):
    __tablename__ = "grupos_empresariais"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Marca(Base):
    __tablename__ = "marcas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(Text, nullable=False)
    nome_mysql = Column(Text)
    grupo_id = Column(UUID(as_uuid=True), ForeignKey("grupos_empresariais.id"), nullable=True)
    aliases = Column(ARRAY(Text), default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Card(Base):
    __tablename__ = "cards"

    id = Column(Text, primary_key=True)
    pipefy_url = Column(Text)
    titulo = Column(Text)
    cliente_id = Column(UUID(as_uuid=True), ForeignKey("marcas.id"), nullable=True)
    concorrente_id = Column(UUID(as_uuid=True), ForeignKey("marcas.id"), nullable=True)
    nome_concorrente_raw = Column(Text)
    nome_cliente_mysql_raw = Column(Text)
    termos_negativados = Column(ARRAY(Text), default=list)
    plataforma = Column(Text)
    status = Column(Text)
    fase_atual = Column(Text)
    data_solicitacao = Column(Date)
    raw_data = Column(JSONB, default=dict)
    processado = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Evidencia(Base):
    __tablename__ = "evidencias"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    card_id = Column(Text, ForeignKey("cards.id", ondelete="CASCADE"))
    nome_original = Column(Text)
    nome_logico = Column(Text)
    url_original = Column(Text)
    url_cache = Column(Text)
    secao_origem = Column(Text)

    marca_identificada = Column(Text)
    concorrente_identificado = Column(Text)
    dominio = Column(Text)
    plataforma = Column(Text)
    tipo_acao = Column(Text)           # negativacao | exclusao_marca
    tipo_correspondencia = Column(Text) # exata | frase | ampla
    nivel_aplicacao = Column(Text)     # conta | campanha | grupo_anuncios
    termos_identificados = Column(ARRAY(Text), default=list)
    tipo_evidencia = Column(Text)
    data_evidencia = Column(Date)
    confirmacao_negativacao = Column(Boolean, default=False)
    confianca = Column(Float, default=0.0)
    ocr_raw = Column(Text)
    analise_ia = Column(JSONB, default=dict)

    embedding = Column(Vector(384))
    hash_arquivo = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Negativacao(Base):
    __tablename__ = "negativacoes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quem_negativou_id = Column(UUID(as_uuid=True), ForeignKey("marcas.id"))
    quem_foi_negativado_id = Column(UUID(as_uuid=True), ForeignKey("marcas.id"))
    evidencia_id = Column(UUID(as_uuid=True), ForeignKey("evidencias.id"))
    card_id = Column(Text, ForeignKey("cards.id"))
    plataforma = Column(Text)
    data_negativacao = Column(Date)
    confirmada = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
