"""Interfaz de escritorio (Tkinter) del Detector de similitud y plagio.
Ejecutar:  python app.py
"""
import math
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from analizador import Documento, analizar, crear_trie_vacias

COLORES_GRUPO = ["#e76f51", "#2a9d8f", "#e9c46a", "#457b9d", "#9b5de5", "#f28482"]


def leer_archivo(ruta):
    for enc in ("utf-8", "latin-1"):
        try:
            with open(ruta, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError("No se pudo leer el archivo")


class VentanaComparacion(tk.Toplevel):
    """Dos documentos lado a lado con los fragmentos coincidentes resaltados."""

    def __init__(self, master, r):
        super().__init__(master)
        self.title(f"{r.doc_a.nombre}  vs  {r.doc_b.nombre}  —  {r.similitud:.1f}%")
        self.geometry("1000x560")
        self.columnconfigure((0, 1), weight=1)
        self.rowconfigure(1, weight=1)
        for col, doc, frags, cob in ((0, r.doc_a, r.fragmentos_a, r.cobertura_a),
                                     (1, r.doc_b, r.fragmentos_b, r.cobertura_b)):
            ttk.Label(self, text=f"{doc.nombre}  ({cob:.1f}% coincide)",
                      font=("TkDefaultFont", 10, "bold")).grid(row=0, column=col, pady=4)
            marco = ttk.Frame(self)
            marco.grid(row=1, column=col, sticky="nsew", padx=4, pady=4)
            marco.rowconfigure(0, weight=1)
            marco.columnconfigure(0, weight=1)
            txt = tk.Text(marco, wrap="word")
            sb = ttk.Scrollbar(marco, command=txt.yview)
            txt.configure(yscrollcommand=sb.set)
            txt.grid(row=0, column=0, sticky="nsew")
            sb.grid(row=0, column=1, sticky="ns")
            txt.insert("1.0", doc.texto)
            txt.tag_configure("coinc", background="#ffd54f")
            for ini, fin in frags:
                txt.tag_add("coinc", f"1.0+{ini}c", f"1.0+{fin}c")
            txt.configure(state="disabled")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Detector de similitud y plagio")
        self.geometry("1100x680")
        self.vacias = crear_trie_vacias()
        self.docs = []
        self.analisis = None
        self._construir()

    # ---------------------------- interfaz ---------------------------- #
    def _construir(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Panel izquierdo: documentos y parámetros
        izq = ttk.Frame(self, padding=8)
        izq.grid(row=0, column=0, sticky="ns")
        ttk.Label(izq, text="Documentos", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        self.lista = tk.Listbox(izq, width=30, height=14, selectmode="extended")
        self.lista.pack(fill="x", pady=4)
        for texto, cmd in (("Cargar archivos .txt", self.cargar_archivos),
                           ("Pegar texto", self.pegar_texto),
                           ("Quitar seleccionados", self.quitar),
                           ("Limpiar todo", self.limpiar)):
            ttk.Button(izq, text=texto, command=cmd).pack(fill="x", pady=1)

        ttk.Separator(izq).pack(fill="x", pady=8)
        ttk.Label(izq, text="Parámetros", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        self.var_n = tk.IntVar(value=3)
        self.var_umbral = tk.IntVar(value=30)
        self.var_aprox = tk.IntVar(value=80)
        fila = ttk.Frame(izq)
        fila.pack(fill="x", pady=2)
        ttk.Label(fila, text="Palabras por fragmento:").pack(side="left")
        ttk.Spinbox(fila, from_=2, to=8, width=4, textvariable=self.var_n).pack(side="right")
        self._slider(izq, "Umbral de similitud (%)", self.var_umbral, 5, 100)
        self._slider(izq, "Sensibilidad a cambios (%)", self.var_aprox, 50, 100)
        ttk.Button(izq, text="ANALIZAR", command=self.analizar).pack(fill="x", pady=(10, 2))
        ttk.Button(izq, text="Exportar reporte", command=self.exportar).pack(fill="x")

        # Panel derecho: ranking + grafo
        der = ttk.Frame(self, padding=8)
        der.grid(row=0, column=1, sticky="nsew")
        der.columnconfigure(0, weight=1)
        der.rowconfigure(1, weight=1)
        der.rowconfigure(3, weight=2)
        ttk.Label(der, text="Ranking de similitud (doble clic para ver lado a lado)",
                  font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.tabla = ttk.Treeview(der, columns=("par", "sim", "estado"), show="headings", height=8)
        for col, txt, ancho in (("par", "Par de documentos", 420), ("sim", "Similitud", 90),
                                ("estado", "Estado", 110)):
            self.tabla.heading(col, text=txt)
            self.tabla.column(col, width=ancho, anchor="w" if col == "par" else "center")
        self.tabla.grid(row=1, column=0, sticky="nsew", pady=4)
        self.tabla.tag_configure("sospechoso", background="#ffcdd2")
        self.tabla.bind("<Double-1>", self.abrir_comparacion)
        self.lbl_grupos = ttk.Label(der, text="Grupos de trabajos parecidos: —", wraplength=700)
        self.lbl_grupos.grid(row=2, column=0, sticky="w", pady=4)
        self.canvas = tk.Canvas(der, bg="white", highlightthickness=1, highlightbackground="#ccc")
        self.canvas.grid(row=3, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda e: self.dibujar_grafo())

    def _slider(self, padre, texto, var, desde, hasta):
        etiqueta = ttk.Label(padre, text=f"{texto}: {var.get()}")
        etiqueta.pack(anchor="w", pady=(6, 0))

        def cambio(v):
            var.set(int(float(v)))
            etiqueta.config(text=f"{texto}: {var.get()}")
        ttk.Scale(padre, from_=desde, to=hasta, variable=var, command=cambio).pack(fill="x")

    # ---------------------------- documentos ---------------------------- #
    def _nombre_unico(self, base):
        nombres = {d.nombre for d in self.docs}
        nombre, k = base, 2
        while nombre in nombres:
            nombre, k = f"{base} ({k})", k + 1
        return nombre

    def _agregar(self, nombre, texto):
        if not texto.strip():
            return
        d = Documento(self._nombre_unico(nombre), texto, self.vacias)
        self.docs.append(d)
        self.lista.insert("end", d.nombre)

    def cargar_archivos(self):
        for ruta in filedialog.askopenfilenames(filetypes=[("Texto", "*.txt"), ("Todos", "*.*")]):
            try:
                self._agregar(os.path.basename(ruta), leer_archivo(ruta))
            except Exception as e:
                messagebox.showerror("Error", f"{ruta}\n{e}")

    def pegar_texto(self):
        v = tk.Toplevel(self)
        v.title("Pegar texto")
        ttk.Label(v, text="Nombre del documento:").pack(anchor="w", padx=8, pady=(8, 0))
        nombre = ttk.Entry(v, width=40)
        nombre.insert(0, f"Texto {len(self.docs) + 1}")
        nombre.pack(fill="x", padx=8)
        txt = tk.Text(v, width=80, height=18, wrap="word")
        txt.pack(padx=8, pady=8, fill="both", expand=True)

        def guardar():
            self._agregar(nombre.get().strip() or "Texto", txt.get("1.0", "end-1c"))
            v.destroy()
        ttk.Button(v, text="Agregar", command=guardar).pack(pady=(0, 8))

    def quitar(self):
        for i in reversed(self.lista.curselection()):
            self.lista.delete(i)
            del self.docs[i]

    def limpiar(self):
        self.lista.delete(0, "end")
        self.docs.clear()
        self.tabla.delete(*self.tabla.get_children())
        self.analisis = None
        self.lbl_grupos.config(text="Grupos de trabajos parecidos: —")
        self.canvas.delete("all")

    # ---------------------------- análisis ---------------------------- #
    def analizar(self):
        if len(self.docs) < 2:
            messagebox.showinfo("Faltan documentos", "Carga al menos dos documentos.")
            return
        try:
            n = max(2, int(self.var_n.get()))
        except (tk.TclError, ValueError):
            n = 3
        self.analisis = analizar(self.docs, n, self.var_aprox.get() / 100)
        self.tabla.delete(*self.tabla.get_children())
        umbral = self.var_umbral.get()
        for k, r in enumerate(self.analisis.resultados):
            sospechoso = r.similitud >= umbral
            self.tabla.insert("", "end", iid=str(k),
                              values=(f"{r.doc_a.nombre}  ↔  {r.doc_b.nombre}",
                                      f"{r.similitud:.1f}%",
                                      "Sospechoso" if sospechoso else "Normal"),
                              tags=("sospechoso",) if sospechoso else ())
        grupos = self.analisis.grafo.grupos(umbral)
        self.lbl_grupos.config(text="Grupos de trabajos parecidos: " +
                               ("; ".join("{" + ", ".join(g) + "}" for g in grupos) or "ninguno"))
        self.dibujar_grafo()

    def abrir_comparacion(self, _evento):
        sel = self.tabla.selection()
        if sel and self.analisis:
            VentanaComparacion(self, self.analisis.resultados[int(sel[0])])

    def dibujar_grafo(self):
        c = self.canvas
        c.delete("all")
        if not self.analisis:
            return
        g, umbral = self.analisis.grafo, self.var_umbral.get()
        nodos = g.nodos()
        w, h = max(c.winfo_width(), 200), max(c.winfo_height(), 150)
        cx, cy, radio = w / 2, h / 2, min(w, h) / 2 - 45
        pos = {nd: (cx + radio * math.cos(2 * math.pi * i / len(nodos) - math.pi / 2),
                    cy + radio * math.sin(2 * math.pi * i / len(nodos) - math.pi / 2))
               for i, nd in enumerate(nodos)}
        color = {}
        for k, grupo in enumerate(g.grupos(umbral)):
            for nd in grupo:
                color[nd] = COLORES_GRUPO[k % len(COLORES_GRUPO)]
        for u, v, peso in g.aristas():
            if peso >= umbral:
                c.create_line(*pos[u], *pos[v], width=1 + peso / 25, fill="#888")
                c.create_text((pos[u][0] + pos[v][0]) / 2, (pos[u][1] + pos[v][1]) / 2,
                              text=f"{peso:.0f}%", fill="#c62828", font=("TkDefaultFont", 9, "bold"))
        for nd, (x, y) in pos.items():
            c.create_oval(x - 12, y - 12, x + 12, y + 12, fill=color.get(nd, "#cfd8dc"), outline="#444")
            c.create_text(x, y + 22, text=nd if len(nd) <= 22 else nd[:20] + "…")

    # ---------------------------- reporte ---------------------------- #
    def exportar(self):
        if not self.analisis:
            messagebox.showinfo("Sin resultados", "Primero ejecuta el análisis.")
            return
        ruta = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Texto", "*.txt")])
        if not ruta:
            return
        umbral = self.var_umbral.get()
        lineas = ["REPORTE DE SIMILITUD", "=" * 60, f"Umbral de sospecha: {umbral}%", ""]
        for r in self.analisis.resultados:
            estado = "SOSPECHOSO" if r.similitud >= umbral else "normal"
            lineas.append(f"{r.doc_a.nombre} <-> {r.doc_b.nombre}: {r.similitud:.1f}%  [{estado}]")
            if r.similitud >= umbral:
                for ini, fin in r.fragmentos_a[:15]:
                    lineas.append(f"    en {r.doc_a.nombre}: «{r.doc_a.texto[ini:fin]}»")
        grupos = self.analisis.grafo.grupos(umbral)
        lineas += ["", "Grupos de trabajos parecidos:"] + \
                  [f"  - {', '.join(g)}" for g in grupos] if grupos else ["", "Sin grupos."]
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("\n".join(lineas))
        messagebox.showinfo("Listo", "Reporte exportado.")


if __name__ == "__main__":
    App().mainloop()
