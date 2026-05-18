"""
Lista de clientes Branddi para filtragem cliente × cliente na fase Sucesso.
"""
import unicodedata
import re

# Fases configuradas para sincronização
FASES_SYNC = [
    {"id": "317821292", "nome": "N2. Mediação",                      "filtrar_clientes": False},
    {"id": "317821332", "nome": "N2. Quarentena - Mediação",         "filtrar_clientes": False},
    {"id": "318834986", "nome": "Tratativas Especiais",               "filtrar_clientes": False},
    {"id": "318834987", "nome": "Quarentena - Tratativas Especiais", "filtrar_clientes": False},
    {"id": "315214253", "nome": "Sucesso",                            "filtrar_clientes": True},
]

FASE_SUCESSO_ID = "315214253"

_NOMES_CLIENTES_RAW = [
    # Camicado
    "Camicado", "Home Style - Camicado", "Home Style Camicado",
    # Cantu / PneuStore
    "PneuStore", "Pneustore", "Cantu",
    # Decor Colors / Ela Decora
    "Decor Colors", "Ela Decora",
    # Grupo Ammo Varejo
    "Artex", "MMartan", "Santista Decora", "Grupo Ammo Varejo",
    # Grupo Buddemeyer
    "Buddemeyer", "Casa Almeida", "Grupo Buddemeyer",
    # Grupo Karsten
    "Karsten", "Trussardi", "Grupo Karsten",
    # Grupo Polishop
    "Be Emotion", "Genis", "iChef", "Polishop", "Polishop VC",
    "Viva Smart Nutrition", "Grupo Polishop",
    # Grupo Víssimo
    "Evino", "Grand Cru", "Grupo Víssimo",
    # Linda Casa
    "Linda Casa",
    # MadeiraMadeira
    "MadeiraMadeira", "Casa Tema", "Cabecasa",
    # Grupo Magalu
    "Kabum", "Consórcio Magalu", "Zattini", "Netshoes",
    "Magazine Luiza", "Grupo Magalu",
    # Solo brands
    "Nespresso", "Pacco", "Pichau", "Samsung", "Westwing",
    # Grupo Brinox
    "Brinox", "Coza", "Grupo Brinox",
    # Grupo Six / BHever / Feg / Astron
    "Grupo Six", "BHever", "Grupo Feg", "Grupo Astron",
    "Dermabrew", "LipoLess", "LipoMax", "MemoBlast", "IQ Blast PRO",
    "VisiumMax", "SugarWise", "Lipo Gummy", "Lipo Corpus",
    "GLP1 MAX", "Sugarclean", "GelatinBurn", "NeuroMax",
    "Neurocept", "Memotril", "Ereturbo",
    # Havan
    "Havan",
    # Salve / outros
    "Salve a Julinha", "Salve o Gui", "Útil em Casa", "3 corações",
    # Grupo Casas Bahia
    "Casas Bahia", "Extra", "Ponto Frio", "Grupo Casas Bahia",
    # Instituto Experience
    "Glyco Harmony", "Gelatine Sculpt", "Gela tide", "Neuro Salt",
    "Instituto Experience",
    # Divvino / eFacil
    "Divvino", "eFacil",
    # Grupo Boticário
    "Beleza na Web", "Boca Rosa", "Boca Rosa Company",
    "Boticário", "Eudora", "Grupo Boticário",
    # Grupo Creamy
    "Creamy", "Grupo Creamy",
    # DPSP
    "DPSP", "Drogaria Pacheco", "Drogaria São Paulo",
    # Granado
    "Granado Pharmácias", "Granado",
    # Grupo Ei beleza
    "Beleza Brasileira", "Hidratei", "Imunehair", "Xô Bafinho",
    "Grupo Ei beleza",
    # Grupo Henry Schein
    "Dental Cremer", "Dental Speed", "Utilidades Clinicas",
    "Simples Dental", "Grupo Henry Schein",
    # Mac Cosmetics
    "Mac Cosmetics",
    # Nuvemshop
    "Nuvemshop", "Tienda Nube Argentina", "Tienda Nube Chile",
    "Tienda Nube Colombia", "Tienda Nube Mexico", "Ecommerce na Prática",
    # Saúde
    "Ollie", "RD Saúde", "Raia", "Drogasil",
    # Beleza
    "Happy Hair", "Taiff", "Mascavo", "AMOBELEZA",
    # Grupo Mundial
    "Grupo Mundial", "Mundial Personal Care", "Impala",
    # Kiko / Vitafor
    "Kiko Milano", "Vitafor",
    # Outros
    "Fran By FR", "Labotrat", "Alpha Co", "Beidê", "BrandMonitor",
    # Cobasi
    "Cobasi", "Petz", "Zee Dog",
    # Core Company
    "Core Company", "Explore Mode", "Fjällräven", "The North Face",
    # Grupo Soma
    "Donna Carioca", "Farmrio Brasil", "Fabula", "Foxton", "Grupo Soma",
    # Grupo La Moda
    "Lança Perfume", "My Favorite Things", "Grupo La Moda",
    # Grupo Riachuelo
    "Carters", "Riachuelo", "Grupo Riachuelo",
    # Moda
    "Insider Store", "Movie Fitness",
    # NSX BET
    "NSX BET", "Betnacional", "Betpix", "Mr. Jack Bet",
    "NSX", "PAGBET", "Tvbet",
    # Arezzo
    "Oficina Reserva", "Reserva", "Arezzo",
    "Privalia", "Sergio K.", "Sergio K",
    # Lifestyle
    "StayCloud", "Usaflex", "World Tennis",
    "Moon Ventures", "Minimal Club", "Hoomy",
    "Premier Pet", "Petite Jolie", "Calçados Bibi",
    # Shouder Group
    "Shoulder", "Oriba", "Haight", "Shouder Group",
    # Educação
    "Algar Telecom", "Alura", "AmorSaúde", "Anota ai", "Brisanet",
    "Red Balloon", "Anhanguera", "Pitágoras", "Anglo", "Unopar", "Cogna",
    "Dr.Consulta", "Flash App", "Flash Beneficios",
    "G4 Educacao", "Gran Cursos Online",
    # Flores
    "Flores Online", "Isabela Flores", "Cestas Michelli",
    "Clube da Giu", "Giuliana Flores", "Nova Flor",
    "Grupo Giuliana Flores", "Grupo Flores Online",
    # Ser Educacional
    "UNAMA", "UNIFAEL", "UNINASSAU", "UNINORTE", "Ser Educacional",
    # Serviços
    "Ticket", "Ticket Log", "Unisa", "V4 Franquia", "Wizard",
    # Financeiro
    "Acordo Certo", "Banco BV", "C6 Bank", "Cielo",
    "Santander Financiamentos", "Santander",
    "Ford", "Icarros", "InfinitePay",
    "Itau", "Itaú", "Mobiauto", "Nomad", "Omie",
    "Stone", "Ton", "Stone Company",
    "Utua", "Webmotors",
    "Banco Modal", "Clear Corretora", "Rico", "XP", "XP Inc.",
    "Clara Fintech", "Bold Snacks", "Buser",
    "Central Intercambio", "Click Sophia", "Copastur", "Corello",
    "Democrata Calçados", "DT3",
    "Eat Clean", "Dux Nutrition",
    "Everest", "Evva Hit",
    "Caffeine Army", "Koala", "Sublyme", "SuperCoffee",
    "Grupo Caffeine Army",
    "GS1 Brasil", "Lilibee", "Loggi", "Loungerie",
    "Grupo Loft", "CredPago",
    "Supley", "Max Titanium", "Probiotica", "Dr. Peanut",
    "Melhor Envio",
    "Outback", "Aussie", "Abbraccio",
    "PagHiper", "Puravida", "Top Invest", "Totall Marcas",
    "Unimed", "WFS Filtros",
    "Cetro Máquinas", "Lorenzetti", "Márcia Sensitiva", "Purpose Paper",
    "Alterdata", "BleyMed", "Bling", "Centro Medico Pastore",
    "Chatguru", "Conta Azul", "Fretebras", "Idwall",
    "Instituto Mauá de Tecnologia", "IOB", "LabData", "Livup",
    "Lumisfera Top Kw", "Lumisfera", "Octadesk", "RD Station",
    "Paulistão Atacadista", "Savegnago",
    "SocialSoul", "Takeblip", "Ticketmaster",
    "Protheus", "TOTVS",
    "Tray", "Mercos", "Bem Bolado", "Sankhya", "Interno",
    "Ferracini", "Carlinhos Maia", "Picpay", "Iclinic",
    "Q2 Ingresso", "Conta Simples",
    "Nubank", "Nubank Ultravioleta", "Nubank Empresa",
    "Domino's Pizza", "New Nutrition",
    "Soldiers Nutrition", "Crefaz", "Mais Mu",
    "Integralmedica", "Nutrify", "Darkness", "Grupo BRG",
    "Flexform", "PneuBest", "Localiza", "Hinode",
    "Ensino Einstein", "Aposta Ganha", "Pangeia96",
    "Renner", "Modernitty", "Dark Lab",
    "Heineken", "Schin", "Lagunitas", "KAISER", "Eisenbahn",
    "Devassa", "Bavária", "Baden Baden", "Amstel", "Blue Moon",
    "Vhita", "Aura Beauty",
    "Kaspersky", "Kaspersky - Brasil", "Kaspersky - Chile",
    "Kaspersky - Colômbia", "Kaspersky - México",
    "Toro Investimentos",
    "Nexa Digi", "Juntos pelo Lipe", "Salve o Dudu", "Kauan tem Cura",
    "Agilize", "Clinicorp", "Pagar.me", "Hiper bet", "Hiper Bet",
    "Grupo Memorial", "Grupo Zelo",
    "Vakinha", "Tha Beauty", "Iugu", "Cacau Show",
    "Grupo Euro17", "CVC", "Red Silver", "Aramis",
    "Buddha Spa", "Ticky",
    "Bio Extratus", "Aneethun", "Chikas", "Grupo Bio Extratus",
    "Central das Bíblias", "Serasa", "Editora Garden",
    "Uol Host", "Beach Park",
    "Bioderma", "Grupo NAOS", "Tintas Verginia", "Planeta Atlantida",
    "iFood", "Casa das Alianças", "WAP", "Brasas",
    "Qualicorp", "DHL", "Medcel",
    "Suhai Seguradora", "CNVW", "Consórcio Embracon", "Embracon",
    "MHNET TELECOM", "Bluefit", "Chaves na Mão", "Farmácias Nissei",
    "Estácio", "Wyden", "Idomed", "Yduqs",
    "Bobbie Goods", "Tramontina", "Guday", "Bellinati Perez",
    "Ropek", "Fluency Academy", "Fastshop", "Gummy Hair",
    "Cobli", "Natura", "Azul Linhas Aéreas",
    "Carolina Herrera", "Guichê Web", "ConLicitação",
    "Royal Face", "GWM", "ExitLag", "Tekbond",
    "Remessa online", "Tiny By Olist", "Locaweb", "Wishin",
    "Quero Bolsa", "PersonalGO", "Viva Sorte", "Gold Spell",
    "Lalamove", "Jolimont", "Devzapp",
    "Viação Águia Branca", "HughesNet", "XP Educação",
    "Hostgator", "Sephora",
    "Alelo", "Grupo Elopar",
    "Laçador de Ofertas", "Parque da Mônica", "Royal Canin",
    "Mari Maria MakeUp", "Elements", "Cléa Store",
    "Banco Inter", "Cial Dun & Bradstreet",
    "GOL", "Gol Linhas Aéreas", "Smiles",
    "JusBrasil",
    "Sofá na Caixa", "Little Duck", "EcoFlame Garden",
    "Grupo Sofá na Caixa",
    "IBCMED", "Panini", "Celcoin", "Orthocrin", "Z-Api",
    "Descomplica", "MRV",
    "Esportes da Sorte", "Tim Residencial", "Buy Ticket",
    "Swile", "Notazz", "UCS", "Digisac",
]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s)


_CLIENTES_NORM: set[str] = {_norm(n) for n in _NOMES_CLIENTES_RAW}
_CLIENTES_SORTED: list[str] = sorted(_CLIENTES_NORM, key=len, reverse=True)


def is_cliente(nome: str | None) -> bool:
    """True se o nome pertence à lista de clientes Branddi."""
    if not nome:
        return False
    n = _norm(nome)
    if not n:
        return False
    if n in _CLIENTES_NORM:
        return True
    for cliente in _CLIENTES_SORTED:
        if len(cliente) >= 5 and (cliente in n or n in cliente):
            return True
    return False
