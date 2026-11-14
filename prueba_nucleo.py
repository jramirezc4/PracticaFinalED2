from analizador import Documento, analizar, levenshtein
from estructuras import MaxHeap

orig = ("La contaminación del aire es uno de los principales problemas ambientales de las grandes ciudades. "
        "El tráfico vehicular genera gran parte de las emisiones. Las autoridades deben promover el transporte público.")
copia = ("El tráfico vehicular genera gran parte de las emisiones. La contaminación del aire es uno de los principales "
         "problemas ambientales de las grandes ciudades. Mi opinión es que hay que sembrar más árboles en los parques.")
mod = ("La polución del aire es uno de los principales problemas ambientales de las grandes ciudades. "
       "Las autoridades tienen que promover el transporte público.")
otro = "El fútbol colombiano tiene una larga historia con grandes jugadores y equipos que han marcado épocas."

docs = [Documento(n, t) for n, t in [("original", orig), ("copia", copia), ("modificado", mod), ("otro", otro)]]
an = analizar(docs)
for r in an.resultados:
    print(f"{r.doc_a.nombre:10s} vs {r.doc_b.nombre:10s} {r.similitud:5.1f}%  frags_b={[r.doc_b.texto[i:f][:30] for i,f in r.fragmentos_b]}")
print("grupos>=40:", an.grafo.grupos(40))
assert levenshtein("kitten", "sitting") == 3
h = MaxHeap()
for x in [5, 1, 9, 3, 7]: h.push(x, x)
assert [h.pop()[0] for _ in range(5)] == [9, 7, 5, 3, 1]
print("OK")
