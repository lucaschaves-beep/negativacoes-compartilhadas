-- Adiciona campos de tipo de ação, correspondência e nível na tabela evidencias
ALTER TABLE evidencias
  ADD COLUMN IF NOT EXISTS tipo_acao TEXT DEFAULT 'negativacao',
  ADD COLUMN IF NOT EXISTS tipo_correspondencia TEXT,
  ADD COLUMN IF NOT EXISTS nivel_aplicacao TEXT;

-- tipo_acao: 'negativacao' | 'exclusao_marca'
-- tipo_correspondencia: 'exata' | 'frase' | 'ampla'
-- nivel_aplicacao: 'conta' | 'campanha' | 'grupo_anuncios'
