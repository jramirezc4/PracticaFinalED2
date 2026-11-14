"""Estructuras de datos propias del proyecto (implementadas desde cero).

- Trie:            filtra palabras vacías (artículos, preposiciones...).
- MaxHeap:         cola de prioridad para el ranking de pares más similares.
- GrafoSimilitud:  grafo no dirigido ponderado (nodo = documento, peso = % similitud).
"""


class _NodoTrie:
    __slots__ = ("hijos", "fin")

    def __init__(self):
        self.hijos = {}
        self.fin = False


class Trie:
    def __init__(self, palabras=()):
        self.raiz = _NodoTrie()
        for p in palabras:
            self.insertar(p)

    def insertar(self, palabra):
        nodo = self.raiz
        for c in palabra:
            nodo = nodo.hijos.setdefault(c, _NodoTrie())
        nodo.fin = True

    def contiene(self, palabra):
        nodo = self.raiz
        for c in palabra:
            nodo = nodo.hijos.get(c)
            if nodo is None:
                return False
        return nodo.fin


class MaxHeap:
    """Heap binario de máximos. Cada elemento es (prioridad, dato)."""

    def __init__(self):
        self._a = []

    def __len__(self):
        return len(self._a)

    def vacio(self):
        return not self._a

    def push(self, prioridad, dato):
        a = self._a
        a.append((prioridad, dato))
        i = len(a) - 1
        while i > 0:                                   # sube
            padre = (i - 1) // 2
            if a[padre][0] >= a[i][0]:
                break
            a[padre], a[i] = a[i], a[padre]
            i = padre

    def pop(self):
        a = self._a
        if not a:
            raise IndexError("heap vacío")
        a[0], a[-1] = a[-1], a[0]
        mayor = a.pop()
        i, n = 0, len(a)
        while True:                                    # baja
            izq, der, m = 2 * i + 1, 2 * i + 2, i
            if izq < n and a[izq][0] > a[m][0]:
                m = izq
            if der < n and a[der][0] > a[m][0]:
                m = der
            if m == i:
                break
            a[m], a[i] = a[i], a[m]
            i = m
        return mayor


class GrafoSimilitud:
    """Grafo no dirigido ponderado con lista de adyacencia."""

    def __init__(self):
        self.ady = {}

    def agregar_nodo(self, nodo):
        self.ady.setdefault(nodo, {})

    def agregar_arista(self, u, v, peso):
        self.agregar_nodo(u)
        self.agregar_nodo(v)
        self.ady[u][v] = peso
        self.ady[v][u] = peso

    def nodos(self):
        return list(self.ady)

    def aristas(self):
        vistos, res = set(), []
        for u, vecinos in self.ady.items():
            for v, w in vecinos.items():
                if (v, u) not in vistos:
                    vistos.add((u, v))
                    res.append((u, v, w))
        return res

    def grupos(self, umbral):
        """Componentes conexas usando solo aristas con peso >= umbral (DFS iterativo).
        Devuelve solo grupos de 2 o más documentos."""
        visitado, grupos = set(), []
        for inicio in self.ady:
            if inicio in visitado:
                continue
            pila, grupo = [inicio], []
            visitado.add(inicio)
            while pila:
                u = pila.pop()
                grupo.append(u)
                for v, w in self.ady[u].items():
                    if w >= umbral and v not in visitado:
                        visitado.add(v)
                        pila.append(v)
            if len(grupo) > 1:
                grupos.append(sorted(grupo))
        return grupos
