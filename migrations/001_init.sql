-- Habilita extensão de vetores (já disponível no Supabase)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grupos empresariais
CREATE TABLE IF NOT EXISTS grupos_empresariais (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Marcas e clientes
CREATE TABLE IF NOT EXISTS marcas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome TEXT NOT NULL,
    nome_mysql TEXT,
    grupo_id UUID REFERENCES grupos_empresariais(id) ON DELETE SET NULL,
    aliases TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_marcas_nome ON marcas (LOWER(nome));

-- Cards do Pipefy
CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    pipefy_url TEXT,
    titulo TEXT,
    cliente_id UUID REFERENCES marcas(id),
    concorrente_id UUID REFERENCES marcas(id),
    nome_concorrente_raw TEXT,
    nome_cliente_mysql_raw TEXT,
    termos_negativados TEXT[] DEFAULT '{}',
    plataforma TEXT,
    status TEXT,
    fase_atual TEXT,
    data_solicitacao DATE,
    raw_data JSONB DEFAULT '{}',
    processado BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Evidências (prints analisados)
CREATE TABLE IF NOT EXISTS evidencias (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    card_id TEXT REFERENCES cards(id) ON DELETE CASCADE,
    nome_original TEXT,
    nome_logico TEXT,
    url_original TEXT,
    url_cache TEXT,
    secao_origem TEXT,

    -- Resultado da análise Gemini
    marca_identificada TEXT,
    concorrente_identificado TEXT,
    dominio TEXT,
    plataforma TEXT,
    termos_identificados TEXT[] DEFAULT '{}',
    tipo_evidencia TEXT,
    data_evidencia DATE,
    confirmacao_negativacao BOOLEAN DEFAULT FALSE,
    confianca FLOAT DEFAULT 0.0,
    ocr_raw TEXT,
    analise_ia JSONB DEFAULT '{}',

    -- Embedding para busca semântica (1536 dims = all-MiniLM-L6-v2 usa 384)
    embedding vector(384),

    hash_arquivo TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evidencias_card ON evidencias(card_id);
CREATE INDEX IF NOT EXISTS idx_evidencias_embedding ON evidencias
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_evidencias_hash ON evidencias(hash_arquivo);

-- Registro de negativações detectadas (grafo)
CREATE TABLE IF NOT EXISTS negativacoes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quem_negativou_id UUID REFERENCES marcas(id),
    quem_foi_negativado_id UUID REFERENCES marcas(id),
    evidencia_id UUID REFERENCES evidencias(id),
    card_id TEXT REFERENCES cards(id),
    plataforma TEXT,
    data_negativacao DATE,
    confirmada BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(quem_negativou_id, quem_foi_negativado_id, plataforma, data_negativacao)
);

CREATE INDEX IF NOT EXISTS idx_neg_quem ON negativacoes(quem_negativou_id);
CREATE INDEX IF NOT EXISTS idx_neg_quem_foi ON negativacoes(quem_foi_negativado_id);
CREATE INDEX IF NOT EXISTS idx_neg_par ON negativacoes(quem_negativou_id, quem_foi_negativado_id);

-- View: boa fé mútua entre marcas
CREATE OR REPLACE VIEW boa_fe_mutua AS
SELECT
    a.quem_negativou_id AS marca_a_id,
    a.quem_foi_negativado_id AS marca_b_id,
    ma.nome AS marca_a_nome,
    mb.nome AS marca_b_nome,
    a.plataforma,
    a.data_negativacao AS a_negativou_em,
    b.data_negativacao AS b_negativou_em,
    a.evidencia_id AS evidencia_a,
    b.evidencia_id AS evidencia_b
FROM negativacoes a
JOIN negativacoes b
    ON a.quem_negativou_id = b.quem_foi_negativado_id
    AND a.quem_foi_negativado_id = b.quem_negativou_id
JOIN marcas ma ON ma.id = a.quem_negativou_id
JOIN marcas mb ON mb.id = a.quem_foi_negativado_id
WHERE a.quem_negativou_id < a.quem_foi_negativado_id;
