from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db, GrupoEmpresarial, Marca

router = APIRouter(prefix="/grupos", tags=["grupos"])


class GrupoCreate(BaseModel):
    nome: str


class MarcaGrupoAssign(BaseModel):
    marca_id: str
    grupo_id: str


@router.get("/")
async def list_grupos(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GrupoEmpresarial).order_by(GrupoEmpresarial.nome))
    grupos = result.scalars().all()

    resposta = []
    for g in grupos:
        marcas_result = await db.execute(
            select(Marca).where(Marca.grupo_id == g.id)
        )
        marcas = marcas_result.scalars().all()
        resposta.append({
            "id": str(g.id),
            "nome": g.nome,
            "marcas": [{"id": str(m.id), "nome": m.nome} for m in marcas],
        })

    return resposta


@router.post("/")
async def create_grupo(body: GrupoCreate, db: AsyncSession = Depends(get_db)):
    grupo = GrupoEmpresarial(nome=body.nome.strip())
    db.add(grupo)
    await db.commit()
    await db.refresh(grupo)
    return {"id": str(grupo.id), "nome": grupo.nome}


@router.post("/assign")
async def assign_marca_to_grupo(body: MarcaGrupoAssign, db: AsyncSession = Depends(get_db)):
    marca = await db.get(Marca, body.marca_id)
    grupo = await db.get(GrupoEmpresarial, body.grupo_id)
    if not marca or not grupo:
        raise HTTPException(status_code=404, detail="Marca ou grupo não encontrado")
    marca.grupo_id = grupo.id
    await db.commit()
    return {"ok": True, "marca": marca.nome, "grupo": grupo.nome}
