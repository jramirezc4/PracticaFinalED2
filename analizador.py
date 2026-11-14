"""Núcleo del detector de similitud: limpieza, Rabin-Karp, Levenshtein, ranking y grafo."""
import re
import unicodedata
from dataclasses import dataclass, field

from estructuras import Trie, MaxHeap, GrafoSimilitud

PALABRAS_VACIAS = """
a al algo algun alguna algunas alguno algunos ante antes aqui asi aun aunque bajo cada como con contra cual cuando
de del desde donde dos durante e el ella ellas ello ellos en entre era eran es esa esas ese eso esos esta estaba
estan estar este esto estos fue fueron ha hacia han hasta hay la las le les lo los mas me mi mis mucho muy nada ni
no nos nosotros o os otra otras otro otros para pero poco por porque que quien se sea segun ser si sin sobre su sus
tambien tan tanto te tiene todo todos tras tu tus un una unas uno unos y ya yo
""".split()


def normalizar(palabra):
    """Minúsculas y sin tildes (para que 'Información' == 'informacion')."""
    p = unicodedata.normalize("NFD", palabra.lower())
    return "".join(c for c in p if unicodedata.category(c) != "Mn")


def crear_trie_vacias():
    return Trie(normalizar(p) for p in PALABRAS_VACIAS)


# --------------------------------------------------------------------------- #
# Documento
# --------------------------------------------------------------------------- #
@dataclass
class Token:
    palabra: str
    inicio: int      # posición en el texto ORIGINAL (para resaltar)
    fin: int
    oracion: int


class Documento:
    def __init__(self, nombre, texto, vacias=None):
        vacias = vacias or crear_trie_vacias()
        self.nombre = nombre
        self.texto = texto
        self.tokens = []
        self.oraciones = []          # lista de listas de índices de token
        for m in re.finditer(r"[^.!?\n]+", texto):
            idxs = []
            for w in re.finditer(r"\w+", m.group()):
                p = normalizar(w.group())
                if vacias.contiene(p):
                    continue
                idxs.append(len(self.tokens))
                self.tokens.append(Token(p, m.start() + w.start(), m.start() + w.end(),
                                         len(self.oraciones)))
            if idxs:
                self.oraciones.append(idxs)
        self.palabras = [t.palabra for t in self.tokens]


# --------------------------------------------------------------------------- #
# Rabin-Karp sobre n-gramas de palabras (hash rodante) + tabla hash
# --------------------------------------------------------------------------- #
MOD = (1 << 61) - 1
BASE = 257


def hash_palabra(p):
    h = 0
    for c in p:
        h = (h * BASE + ord(c)) % MOD
    return h


def hashes_ngramas(palabras, n):
    """Hash rodante de cada ventana de n palabras (Rabin-Karp)."""
    if n <= 0 or len(palabras) < n:
        return []
    hp = [hash_palabra(p) for p in palabras]
    pot = pow(BASE, n - 1, MOD)
    h = 0
    for k in range(n):
        h = (h * BASE + hp[k]) % MOD
    res = [h]
    for i in range(len(hp) - n):
        h = ((h - hp[i] * pot) * BASE + hp[i + n]) % MOD
        res.append(h)
    return res


def construir_tabla(palabras, n):
    """Tabla hash: hash del n-grama -> posiciones donde aparece."""
    tabla = {}
    for i, h in enumerate(hashes_ngramas(palabras, n)):
        tabla.setdefault(h, []).append(i)
    return tabla


def coincidencias_exactas(a, b, n):
    """Índices de tokens de A y B cubiertos por n-gramas idénticos."""
    tabla_a = construir_tabla(a.palabras, n)
    cub_a, cub_b = set(), set()
    for j, h in enumerate(hashes_ngramas(b.palabras, n)):
        for i in tabla_a.get(h, ()):
            if a.palabras[i:i + n] == b.palabras[j:j + n]:   # descarta colisiones
                cub_a.update(range(i, i + n))
                cub_b.update(range(j, j + n))
    return cub_a, cub_b


# --------------------------------------------------------------------------- #
# Levenshtein (copias con pequeñas modificaciones)
# --------------------------------------------------------------------------- #
def levenshtein(s, t):
    if len(s) < len(t):
        s, t = t, s
    prev = list(range(len(t) + 1))
    for i, cs in enumerate(s, 1):
        act = [i]
        for j, ct in enumerate(t, 1):
            act.append(min(prev[j] + 1, act[j - 1] + 1, prev[j - 1] + (cs != ct)))
        prev = act
    return prev[-1]


def similitud_levenshtein(s, t):
    m = max(len(s), len(t))
    return 1.0 if m == 0 else 1 - levenshtein(s, t) / m


def _oraciones_parecidas(pa, pb, umbral):
    """pa, pb: listas de palabras de una oración. Cubre cambios de palabras (Levenshtein)
    y cambios de orden (Jaccard sobre el conjunto de palabras)."""
    if min(len(pa), len(pb)) / max(len(pa), len(pb)) < 0.6:      # filtro rápido
        return False
    sa, sb = set(pa), set(pb)
    if len(sa & sb) / len(sa | sb) >= umbral:
        return True
    return similitud_levenshtein(" ".join(pa), " ".join(pb)) >= umbral


def coincidencias_aproximadas(a, b, n, umbral, cub_a, cub_b):
    """Compara oraciones aún no cubiertas del todo. Devuelve nuevos cubiertos."""
    nuevo_a, nuevo_b = set(), set()
    for oa in a.oraciones:
        if len(oa) < max(n, 4) or all(i in cub_a for i in oa):
            continue
        pa = [a.palabras[i] for i in oa]
        for ob in b.oraciones:
            if len(ob) < max(n, 4) or all(j in cub_b for j in ob):
                continue
            pb = [b.palabras[j] for j in ob]
            if _oraciones_parecidas(pa, pb, umbral):
                nuevo_a.update(oa)
                nuevo_b.update(ob)
    return nuevo_a, nuevo_b


# --------------------------------------------------------------------------- #
# Comparación de pares, ranking y grafo
# --------------------------------------------------------------------------- #
def _rangos(doc, cubiertos):
    """Convierte tokens cubiertos en rangos (inicio, fin) de caracteres del texto original."""
    rangos, grupo = [], []
    for i in sorted(cubiertos):
        if grupo and (i != grupo[-1] + 1 or doc.tokens[i].oracion != doc.tokens[grupo[-1]].oracion):
            rangos.append((doc.tokens[grupo[0]].inicio, doc.tokens[grupo[-1]].fin))
            grupo = []
        grupo.append(i)
    if grupo:
        rangos.append((doc.tokens[grupo[0]].inicio, doc.tokens[grupo[-1]].fin))
    return rangos


@dataclass
class Resultado:
    doc_a: Documento
    doc_b: Documento
    similitud: float          # 0-100
    cobertura_a: float
    cobertura_b: float
    fragmentos_a: list = field(default_factory=list)
    fragmentos_b: list = field(default_factory=list)


def comparar(a, b, n=3, umbral_aprox=0.8):
    cub_a, cub_b = coincidencias_exactas(a, b, n)
    na, nb = coincidencias_aproximadas(a, b, n, umbral_aprox, cub_a, cub_b)
    cub_a |= na
    cub_b |= nb
    cob_a = 100 * len(cub_a) / len(a.tokens) if a.tokens else 0.0
    cob_b = 100 * len(cub_b) / len(b.tokens) if b.tokens else 0.0
    # Si un trabajo pequeño está copiado dentro de uno grande, el pequeño tiene ~100%
    # y eso es lo que debe reportarse: por eso se toma el máximo de ambas coberturas.
    return Resultado(a, b, max(cob_a, cob_b), cob_a, cob_b,
                     _rangos(a, cub_a), _rangos(b, cub_b))


@dataclass
class Analisis:
    resultados: list          # ordenados de mayor a menor similitud (salen del heap)
    grafo: GrafoSimilitud


def analizar(documentos, n=3, umbral_aprox=0.8):
    heap, grafo = MaxHeap(), GrafoSimilitud()
    for d in documentos:
        grafo.agregar_nodo(d.nombre)
    for i in range(len(documentos)):
        for j in range(i + 1, len(documentos)):
            r = comparar(documentos[i], documentos[j], n, umbral_aprox)
            heap.push(r.similitud, r)
            grafo.agregar_arista(documentos[i].nombre, documentos[j].nombre, r.similitud)
    ordenados = []
    while not heap.vacio():
        ordenados.append(heap.pop()[1])
    return Analisis(ordenados, grafo)
