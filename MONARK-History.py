"""
Verificador de Cuentas por Correo Electrónico (OSINT)
=======================================================
Interfaz gráfica en CustomTkinter que usa la LIBRERÍA de Holehe
(no la línea de comandos) para revisar en qué plataformas está
registrado un correo electrónico.

Novedades de esta versión:
  - Buscador con autocompletado para revisar SOLO sitios
    específicos (ej: escribe "fa" y te sugiere "fanpop", etc.)
    en vez de las ~120 plataformas completas.
  - Filtro de orden: por nombre (A-Z / Z-A) o por fecha de
    creación de la cuenta cuando el sitio la entrega (ver nota
    abajo, la mayoría de sitios NO exponen esa fecha).

Cómo funciona Holehe: consulta el formulario de "olvidé mi
contraseña" o de registro de cada sitio y observa la respuesta
pública. NO envía correos ni alerta a nadie.

NOTA IMPORTANTE sobre "ordenar por fecha":
  Holehe solo puede mostrar una fecha real de creación de cuenta
  en muy pocos módulos (actualmente solo ProtonMail la expone a
  través de su API pública). El resto de sitios (Spotify, GitHub,
  Amazon, etc.) NO devuelven esa fecha por diseño de sus propias
  APIs. Por eso, al ordenar "por fecha", los resultados CON fecha
  disponible aparecen primero según el criterio elegido, y el
  resto se ordena alfabéticamente al final (no hay fecha que
  ordenar para ellos).

Requisitos (instalar antes de ejecutar):
    pip install customtkinter holehe

(trio y httpx se instalan automáticamente como dependencias de holehe)

Uso:
    python verificador_cuentas.py
"""

from datetime import datetime

import customtkinter as ctk

try:
    import trio
    import httpx
    from holehe.core import import_submodules, get_functions
    HOLEHE_DISPONIBLE = True
except ImportError:
    HOLEHE_DISPONIBLE = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLOR_ICONO = {
    "encontrado": ("#1f8b4c", "✅"),
    "no_encontrado": ("#666666", "—"),
    "rate_limit": ("#c9822a", "⏱️"),
}

OPCIONES_ORDEN = [
    "Nombre (A-Z)",
    "Nombre (Z-A)",
    "Fecha (más reciente primero)",
    "Fecha (más antigua primero)",
]


def extraer_fecha(resultado):
    """Devuelve datetime si el módulo entregó fecha de creación, si no None."""
    others = resultado.get("others")
    if not others or not isinstance(others, dict):
        return None
    valor = others.get("Date, time of the creation")
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


class VerificadorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Verificador de Cuentas - OSINT (Holehe)")
        self.geometry("700x760")
        self.minsize(620, 600)

        self.sitios_seleccionados = set()
        self.todas_las_funciones = []
        self.nombres_disponibles = []
        self.contadores = {"encontrado": 0, "no_encontrado": 0, "rate_limit": 0}

        self._construir_interfaz()

        if HOLEHE_DISPONIBLE:
            self._cargar_modulos_holehe()
        else:
            self.label_estado.configure(
                text="❌ No se encontró 'holehe'. Instálalo con: pip install customtkinter holehe",
                text_color="red",
            )

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def _construir_interfaz(self):
        ctk.CTkLabel(
            self, text="Verificador de Cuentas por Email",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            self, text="Powered by Holehe — revisa ~120 plataformas",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(pady=(0, 15))

        # --- Entrada de correo ---
        frame_input = ctk.CTkFrame(self, fg_color="transparent")
        frame_input.pack(pady=5, padx=20, fill="x")

        self.entry_email = ctk.CTkEntry(
            frame_input, placeholder_text="correo@ejemplo.com", height=38
        )
        self.entry_email.pack(side="left", padx=(0, 10), expand=True, fill="x")
        self.entry_email.bind("<Return>", lambda e: self.iniciar_verificacion())

        self.btn_verificar = ctk.CTkButton(
            frame_input, text="Verificar", width=120, height=38,
            command=self.iniciar_verificacion
        )
        self.btn_verificar.pack(side="left")

        # --- Buscador de sitio específico con autocompletado ---
        frame_sitios = ctk.CTkFrame(self, fg_color="transparent")
        frame_sitios.pack(pady=(10, 0), padx=20, fill="x")

        ctk.CTkLabel(
            frame_sitios,
            text="Sitio(s) específico(s) a revisar (opcional — vacío = revisar todos):",
            font=ctk.CTkFont(size=12), text_color="gray", anchor="w"
        ).pack(fill="x")

        self.entry_sitio = ctk.CTkEntry(
            frame_sitios, placeholder_text="Escribe, ej: fa, git, spot...", height=32
        )
        self.entry_sitio.pack(fill="x", pady=(2, 0))
        self.entry_sitio.bind("<KeyRelease>", self.actualizar_sugerencias)

        self.frame_sugerencias = ctk.CTkFrame(frame_sitios, fg_color="transparent")
        self.frame_sugerencias.pack(fill="x", pady=(2, 0))

        ctk.CTkLabel(
            frame_sitios, text="Sitios seleccionados:",
            font=ctk.CTkFont(size=11), text_color="gray"
        ).pack(anchor="w", pady=(5, 0))

        self.frame_seleccionados = ctk.CTkFrame(frame_sitios, fg_color="transparent")
        self.frame_seleccionados.pack(fill="x")

        # --- Opciones: mostrar todo + orden ---
        frame_opciones = ctk.CTkFrame(self, fg_color="transparent")
        frame_opciones.pack(pady=(12, 0), padx=20, fill="x")

        self.mostrar_todo = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            frame_opciones, text="Mostrar también los NO registrados",
            variable=self.mostrar_todo
        ).pack(side="left")

        ctk.CTkLabel(frame_opciones, text="  Ordenar por:").pack(side="left", padx=(15, 5))
        self.combo_orden = ctk.CTkComboBox(
            frame_opciones, values=OPCIONES_ORDEN, width=230, state="readonly"
        )
        self.combo_orden.set(OPCIONES_ORDEN[0])
        self.combo_orden.pack(side="left")

        # --- Barra de progreso ---
        self.progress = ctk.CTkProgressBar(self, width=640, mode="indeterminate")
        self.progress.pack(pady=(15, 5))

        self.label_estado = ctk.CTkLabel(self, text="Cargando módulos de Holehe...", text_color="gray")
        self.label_estado.pack(pady=(0, 10))

        # --- Resultados ---
        self.frame_resultados = ctk.CTkScrollableFrame(self, width=650, height=330)
        self.frame_resultados.pack(pady=10, padx=20, fill="both", expand=True)

    # ------------------------------------------------------------------
    # Carga de módulos disponibles (para el autocompletado)
    # ------------------------------------------------------------------
    def _cargar_modulos_holehe(self):
        try:
            modulos = import_submodules("holehe.modules")
            self.todas_las_funciones = sorted(get_functions(modulos), key=lambda f: f.__name__)
            self.nombres_disponibles = [f.__name__ for f in self.todas_las_funciones]
            self.label_estado.configure(
                text=f"Listo — {len(self.nombres_disponibles)} plataformas disponibles",
                text_color="gray",
            )
        except Exception as e:
            self.label_estado.configure(text=f"❌ Error cargando Holehe: {e}", text_color="red")

    # ------------------------------------------------------------------
    # Autocompletado de sitios
    # ------------------------------------------------------------------
    def actualizar_sugerencias(self, event=None):
        for w in self.frame_sugerencias.winfo_children():
            w.destroy()

        texto = self.entry_sitio.get().strip().lower()
        if not texto or not self.nombres_disponibles:
            return

        coincidencias = [n for n in self.nombres_disponibles if texto in n.lower()][:10]
        if not coincidencias:
            ctk.CTkLabel(
                self.frame_sugerencias, text="Sin coincidencias",
                text_color="gray", font=ctk.CTkFont(size=11)
            ).pack(side="left", padx=3)
            return

        for nombre in coincidencias:
            ctk.CTkButton(
                self.frame_sugerencias, text=nombre, height=24,
                fg_color="#333333", hover_color="#3f51b5",
                command=lambda n=nombre: self.agregar_sitio(n)
            ).pack(side="left", padx=3, pady=2)

    def agregar_sitio(self, nombre):
        self.sitios_seleccionados.add(nombre)
        self.entry_sitio.delete(0, "end")
        for w in self.frame_sugerencias.winfo_children():
            w.destroy()
        self._refrescar_chips()

    def quitar_sitio(self, nombre):
        self.sitios_seleccionados.discard(nombre)
        self._refrescar_chips()

    def _refrescar_chips(self):
        for w in self.frame_seleccionados.winfo_children():
            w.destroy()
        for nombre in sorted(self.sitios_seleccionados):
            ctk.CTkButton(
                self.frame_seleccionados, text=f"{nombre}  ✕", height=24,
                fg_color="#1f5c8b", hover_color="#c0392b",
                command=lambda n=nombre: self.quitar_sitio(n)
            ).pack(side="left", padx=3, pady=2)

    # ------------------------------------------------------------------
    # Resultados: limpiar / agregar fila
    # ------------------------------------------------------------------
    def limpiar_resultados(self):
        for widget in self.frame_resultados.winfo_children():
            widget.destroy()
        self.contadores = {"encontrado": 0, "no_encontrado": 0, "rate_limit": 0}

    def agregar_resultado(self, resultado):
        if resultado.get("rateLimit"):
            estado = "rate_limit"
        elif resultado.get("exists"):
            estado = "encontrado"
        else:
            estado = "no_encontrado"

        color, icono = COLOR_ICONO[estado]

        fila = ctk.CTkFrame(self.frame_resultados, fg_color="transparent")
        fila.pack(fill="x", pady=2, padx=5)

        fila_principal = ctk.CTkFrame(fila, fg_color="transparent")
        fila_principal.pack(fill="x")

        ctk.CTkLabel(fila_principal, text=icono, width=30).pack(side="left")
        ctk.CTkLabel(
            fila_principal, text=resultado.get("domain") or resultado["name"],
            anchor="w", width=350
        ).pack(side="left", padx=5)
        ctk.CTkLabel(
            fila_principal, text=estado.replace("_", " ").capitalize(),
            text_color=color, anchor="e"
        ).pack(side="right", padx=5)

        # Detalles extra: fecha de creación (si existe), recuperación, nombre
        detalles = []
        fecha = extraer_fecha(resultado)
        if fecha:
            detalles.append(f"Creado: {fecha.strftime('%Y-%m-%d %H:%M')}")
        if resultado.get("emailrecovery"):
            detalles.append(f"Recuperación: {resultado['emailrecovery']}")
        others = resultado.get("others")
        if isinstance(others, dict) and others.get("FullName"):
            detalles.append(f"Nombre: {others['FullName']}")

        if detalles:
            ctk.CTkLabel(
                fila, text="   " + "  |  ".join(detalles),
                font=ctk.CTkFont(size=11), text_color="#999999", anchor="w"
            ).pack(fill="x", padx=35)

        self.contadores[estado] += 1

    # ------------------------------------------------------------------
    # Orden de resultados
    # ------------------------------------------------------------------
    def ordenar_resultados(self, resultados):
        criterio = self.combo_orden.get()

        if criterio == "Nombre (A-Z)":
            return sorted(resultados, key=lambda r: r["name"])
        if criterio == "Nombre (Z-A)":
            return sorted(resultados, key=lambda r: r["name"], reverse=True)

        # Ordenar por fecha: los que sí tienen fecha van primero (según el
        # criterio elegido), el resto se ordena alfabéticamente al final
        # porque Holehe no expone fecha para esos sitios.
        reciente_primero = criterio == "Fecha (más reciente primero)"
        con_fecha = [r for r in resultados if extraer_fecha(r) is not None]
        sin_fecha = [r for r in resultados if extraer_fecha(r) is None]
        con_fecha.sort(key=extraer_fecha, reverse=reciente_primero)
        sin_fecha.sort(key=lambda r: r["name"])
        return con_fecha + sin_fecha

    # ------------------------------------------------------------------
    # Verificación (hilo + trio)
    # ------------------------------------------------------------------
    def iniciar_verificacion(self):
        email = self.entry_email.get().strip()
        if not email or "@" not in email:
            self.label_estado.configure(text="⚠️ Ingresa un correo válido", text_color="orange")
            return

        if not HOLEHE_DISPONIBLE:
            self.label_estado.configure(
                text="❌ Holehe no está instalado. pip install customtkinter holehe",
                text_color="red",
            )
            return

        if self.sitios_seleccionados:
            funciones = [f for f in self.todas_las_funciones if f.__name__ in self.sitios_seleccionados]
        else:
            funciones = self.todas_las_funciones

        if not funciones:
            self.label_estado.configure(text="⚠️ No hay sitios para revisar", text_color="orange")
            return

        self.limpiar_resultados()
        self.btn_verificar.configure(state="disabled", text="Verificando...")
        self.label_estado.configure(
            text=f"Consultando {len(funciones)} plataforma(s) para {email}...",
            text_color="gray",
        )
        self.progress.start()

        import threading
        threading.Thread(target=self.ejecutar_verificacion, args=(email, funciones), daemon=True).start()

    def ejecutar_verificacion(self, email, funciones):
        try:
            resultados = trio.run(self._revisar_async, email, funciones)
        except Exception as e:
            self.after(0, lambda: self.mostrar_error_general(str(e)))
            return
        self.after(0, lambda: self.procesar_resultados(resultados, email))

    async def _revisar_async(self, email, funciones):
        resultados = []
        async with httpx.AsyncClient(timeout=15) as client:
            async with trio.open_nursery() as nursery:
                for funcion in funciones:
                    nursery.start_soon(self._ejecutar_modulo, funcion, email, client, resultados)
        return resultados

    @staticmethod
    async def _ejecutar_modulo(funcion, email, client, out):
        try:
            await funcion(email, client, out)
        except Exception:
            out.append({
                "name": funcion.__name__, "domain": funcion.__name__,
                "rateLimit": True, "exists": False,
                "emailrecovery": None, "phoneNumber": None, "others": None,
            })

    def procesar_resultados(self, resultados, email):
        if not self.mostrar_todo.get():
            resultados = [r for r in resultados if r.get("exists")]

        resultados = self.ordenar_resultados(resultados)

        for r in resultados:
            self.agregar_resultado(r)

        if not resultados:
            ctk.CTkLabel(
                self.frame_resultados, text="Sin resultados para mostrar con los filtros actuales",
                text_color="gray"
            ).pack(pady=10)

        self.progress.stop()
        self.btn_verificar.configure(state="normal", text="Verificar")
        self.label_estado.configure(
            text=(
                f"Listo — {self.contadores['encontrado']} encontrada(s) | "
                f"{self.contadores['rate_limit']} con límite | "
                f"correo: {email}"
            ),
            text_color="#1f8b4c",
        )

    def mostrar_error_general(self, mensaje):
        self.progress.stop()
        self.btn_verificar.configure(state="normal", text="Verificar")
        self.label_estado.configure(text=f"❌ Error: {mensaje}", text_color="red")


if __name__ == "__main__":
    app = VerificadorApp()
    app.mainloop()
"""
Verificador de Cuentas por Correo Electrónico - MONARK-History (OSINT)
=======================================================
Interfaz gráfica en CustomTkinter que usa la LIBRERÍA de Holehe
(no la línea de comandos) para revisar en qué plataformas está
registrado un correo electrónico.

Novedades de esta versión:
  - Buscador con autocompletado para revisar SOLO sitios
    específicos (ej: escribe "fa" y te sugiere "fanpop", etc.)
    en vez de las ~120 plataformas completas.
  - Filtro de orden: por nombre (A-Z / Z-A) o por fecha de
    creación de la cuenta cuando el sitio la entrega (ver nota
    abajo, la mayoría de sitios NO exponen esa fecha).

Cómo funciona Holehe: consulta el formulario de "olvidé mi
contraseña" o de registro de cada sitio y observa la respuesta
pública. NO envía correos ni alerta a nadie.

NOTA IMPORTANTE sobre "ordenar por fecha":
  Holehe solo puede mostrar una fecha real de creación de cuenta
  en muy pocos módulos (actualmente solo ProtonMail la expone a
  través de su API pública). El resto de sitios (Spotify, GitHub,
  Amazon, etc.) NO devuelven esa fecha por diseño de sus propias
  APIs. Por eso, al ordenar "por fecha", los resultados CON fecha
  disponible aparecen primero según el criterio elegido, y el
  resto se ordena alfabéticamente al final (no hay fecha que
  ordenar para ellos).

Requisitos (instalar antes de ejecutar):
    pip install customtkinter holehe

(trio y httpx se instalan automáticamente como dependencias de holehe)

Uso:
    python MONARK-History.py
"""

from datetime import datetime

import customtkinter as ctk

try:
    import trio
    import httpx
    from holehe.core import import_submodules, get_functions
    HOLEHE_DISPONIBLE = True
except ImportError:
    HOLEHE_DISPONIBLE = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLOR_ICONO = {
    "encontrado": ("#1f8b4c", "✅"),
    "no_encontrado": ("#666666", "—"),
    "rate_limit": ("#c9822a", "⏱️"),
}

OPCIONES_ORDEN = [
    "Nombre (A-Z)",
    "Nombre (Z-A)",
    "Fecha (más reciente primero)",
    "Fecha (más antigua primero)",
]


def extraer_fecha(resultado):
    """Devuelve datetime si el módulo entregó fecha de creación, si no None."""
    others = resultado.get("others")
    if not others or not isinstance(others, dict):
        return None
    valor = others.get("Date, time of the creation")
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


class VerificadorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Verificador de Cuentas - OSINT (Holehe)")
        self.geometry("700x760")
        self.minsize(620, 600)

        self.sitios_seleccionados = set()
        self.todas_las_funciones = []
        self.nombres_disponibles = []
        self.contadores = {"encontrado": 0, "no_encontrado": 0, "rate_limit": 0}

        self._construir_interfaz()

        if HOLEHE_DISPONIBLE:
            self._cargar_modulos_holehe()
        else:
            self.label_estado.configure(
                text="❌ No se encontró 'holehe'. Instálalo con: pip install customtkinter holehe",
                text_color="red",
            )

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def _construir_interfaz(self):
        ctk.CTkLabel(
            self, text="Verificador de Cuentas por Email",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            self, text="Powered by Holehe — revisa ~120 plataformas",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(pady=(0, 15))

        # --- Entrada de correo ---
        frame_input = ctk.CTkFrame(self, fg_color="transparent")
        frame_input.pack(pady=5, padx=20, fill="x")

        self.entry_email = ctk.CTkEntry(
            frame_input, placeholder_text="correo@ejemplo.com", height=38
        )
        self.entry_email.pack(side="left", padx=(0, 10), expand=True, fill="x")
        self.entry_email.bind("<Return>", lambda e: self.iniciar_verificacion())

        self.btn_verificar = ctk.CTkButton(
            frame_input, text="Verificar", width=120, height=38,
            command=self.iniciar_verificacion
        )
        self.btn_verificar.pack(side="left")

        # --- Buscador de sitio específico con autocompletado ---
        frame_sitios = ctk.CTkFrame(self, fg_color="transparent")
        frame_sitios.pack(pady=(10, 0), padx=20, fill="x")

        ctk.CTkLabel(
            frame_sitios,
            text="Sitio(s) específico(s) a revisar (opcional — vacío = revisar todos):",
            font=ctk.CTkFont(size=12), text_color="gray", anchor="w"
        ).pack(fill="x")

        self.entry_sitio = ctk.CTkEntry(
            frame_sitios, placeholder_text="Escribe, ej: fa, git, spot...", height=32
        )
        self.entry_sitio.pack(fill="x", pady=(2, 0))
        self.entry_sitio.bind("<KeyRelease>", self.actualizar_sugerencias)

        self.frame_sugerencias = ctk.CTkFrame(frame_sitios, fg_color="transparent")
        self.frame_sugerencias.pack(fill="x", pady=(2, 0))

        ctk.CTkLabel(
            frame_sitios, text="Sitios seleccionados:",
            font=ctk.CTkFont(size=11), text_color="gray"
        ).pack(anchor="w", pady=(5, 0))

        self.frame_seleccionados = ctk.CTkFrame(frame_sitios, fg_color="transparent")
        self.frame_seleccionados.pack(fill="x")

        # --- Opciones: mostrar todo + orden ---
        frame_opciones = ctk.CTkFrame(self, fg_color="transparent")
        frame_opciones.pack(pady=(12, 0), padx=20, fill="x")

        self.mostrar_todo = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            frame_opciones, text="Mostrar también los NO registrados",
            variable=self.mostrar_todo
        ).pack(side="left")

        ctk.CTkLabel(frame_opciones, text="  Ordenar por:").pack(side="left", padx=(15, 5))
        self.combo_orden = ctk.CTkComboBox(
            frame_opciones, values=OPCIONES_ORDEN, width=230, state="readonly"
        )
        self.combo_orden.set(OPCIONES_ORDEN[0])
        self.combo_orden.pack(side="left")

        # --- Barra de progreso ---
        self.progress = ctk.CTkProgressBar(self, width=640, mode="indeterminate")
        self.progress.pack(pady=(15, 5))

        self.label_estado = ctk.CTkLabel(self, text="Cargando módulos de Holehe...", text_color="gray")
        self.label_estado.pack(pady=(0, 10))

        # --- Resultados ---
        self.frame_resultados = ctk.CTkScrollableFrame(self, width=650, height=330)
        self.frame_resultados.pack(pady=10, padx=20, fill="both", expand=True)

    # ------------------------------------------------------------------
    # Carga de módulos disponibles (para el autocompletado)
    # ------------------------------------------------------------------
    def _cargar_modulos_holehe(self):
        try:
            modulos = import_submodules("holehe.modules")
            self.todas_las_funciones = sorted(get_functions(modulos), key=lambda f: f.__name__)
            self.nombres_disponibles = [f.__name__ for f in self.todas_las_funciones]
            self.label_estado.configure(
                text=f"Listo — {len(self.nombres_disponibles)} plataformas disponibles",
                text_color="gray",
            )
        except Exception as e:
            self.label_estado.configure(text=f"❌ Error cargando Holehe: {e}", text_color="red")

    # ------------------------------------------------------------------
    # Autocompletado de sitios
    # ------------------------------------------------------------------
    def actualizar_sugerencias(self, event=None):
        for w in self.frame_sugerencias.winfo_children():
            w.destroy()

        texto = self.entry_sitio.get().strip().lower()
        if not texto or not self.nombres_disponibles:
            return

        coincidencias = [n for n in self.nombres_disponibles if texto in n.lower()][:10]
        if not coincidencias:
            ctk.CTkLabel(
                self.frame_sugerencias, text="Sin coincidencias",
                text_color="gray", font=ctk.CTkFont(size=11)
            ).pack(side="left", padx=3)
            return

        for nombre in coincidencias:
            ctk.CTkButton(
                self.frame_sugerencias, text=nombre, height=24,
                fg_color="#333333", hover_color="#3f51b5",
                command=lambda n=nombre: self.agregar_sitio(n)
            ).pack(side="left", padx=3, pady=2)

    def agregar_sitio(self, nombre):
        self.sitios_seleccionados.add(nombre)
        self.entry_sitio.delete(0, "end")
        for w in self.frame_sugerencias.winfo_children():
            w.destroy()
        self._refrescar_chips()

    def quitar_sitio(self, nombre):
        self.sitios_seleccionados.discard(nombre)
        self._refrescar_chips()

    def _refrescar_chips(self):
        for w in self.frame_seleccionados.winfo_children():
            w.destroy()
        for nombre in sorted(self.sitios_seleccionados):
            ctk.CTkButton(
                self.frame_seleccionados, text=f"{nombre}  ✕", height=24,
                fg_color="#1f5c8b", hover_color="#c0392b",
                command=lambda n=nombre: self.quitar_sitio(n)
            ).pack(side="left", padx=3, pady=2)

    # ------------------------------------------------------------------
    # Resultados: limpiar / agregar fila
    # ------------------------------------------------------------------
    def limpiar_resultados(self):
        for widget in self.frame_resultados.winfo_children():
            widget.destroy()
        self.contadores = {"encontrado": 0, "no_encontrado": 0, "rate_limit": 0}

    def agregar_resultado(self, resultado):
        if resultado.get("rateLimit"):
            estado = "rate_limit"
        elif resultado.get("exists"):
            estado = "encontrado"
        else:
            estado = "no_encontrado"

        color, icono = COLOR_ICONO[estado]

        fila = ctk.CTkFrame(self.frame_resultados, fg_color="transparent")
        fila.pack(fill="x", pady=2, padx=5)

        fila_principal = ctk.CTkFrame(fila, fg_color="transparent")
        fila_principal.pack(fill="x")

        ctk.CTkLabel(fila_principal, text=icono, width=30).pack(side="left")
        ctk.CTkLabel(
            fila_principal, text=resultado.get("domain") or resultado["name"],
            anchor="w", width=350
        ).pack(side="left", padx=5)
        ctk.CTkLabel(
            fila_principal, text=estado.replace("_", " ").capitalize(),
            text_color=color, anchor="e"
        ).pack(side="right", padx=5)

        # Detalles extra: fecha de creación (si existe), recuperación, nombre
        detalles = []
        fecha = extraer_fecha(resultado)
        if fecha:
            detalles.append(f"Creado: {fecha.strftime('%Y-%m-%d %H:%M')}")
        if resultado.get("emailrecovery"):
            detalles.append(f"Recuperación: {resultado['emailrecovery']}")
        others = resultado.get("others")
        if isinstance(others, dict) and others.get("FullName"):
            detalles.append(f"Nombre: {others['FullName']}")

        if detalles:
            ctk.CTkLabel(
                fila, text="   " + "  |  ".join(detalles),
                font=ctk.CTkFont(size=11), text_color="#999999", anchor="w"
            ).pack(fill="x", padx=35)

        self.contadores[estado] += 1

    # ------------------------------------------------------------------
    # Orden de resultados
    # ------------------------------------------------------------------
    def ordenar_resultados(self, resultados):
        criterio = self.combo_orden.get()

        if criterio == "Nombre (A-Z)":
            return sorted(resultados, key=lambda r: r["name"])
        if criterio == "Nombre (Z-A)":
            return sorted(resultados, key=lambda r: r["name"], reverse=True)

        # Ordenar por fecha: los que sí tienen fecha van primero (según el
        # criterio elegido), el resto se ordena alfabéticamente al final
        # porque Holehe no expone fecha para esos sitios.
        reciente_primero = criterio == "Fecha (más reciente primero)"
        con_fecha = [r for r in resultados if extraer_fecha(r) is not None]
        sin_fecha = [r for r in resultados if extraer_fecha(r) is None]
        con_fecha.sort(key=extraer_fecha, reverse=reciente_primero)
        sin_fecha.sort(key=lambda r: r["name"])
        return con_fecha + sin_fecha

    # ------------------------------------------------------------------
    # Verificación (hilo + trio)
    # ------------------------------------------------------------------
    def iniciar_verificacion(self):
        email = self.entry_email.get().strip()
        if not email or "@" not in email:
            self.label_estado.configure(text="⚠️ Ingresa un correo válido", text_color="orange")
            return

        if not HOLEHE_DISPONIBLE:
            self.label_estado.configure(
                text="❌ Holehe no está instalado. pip install customtkinter holehe",
                text_color="red",
            )
            return

        if self.sitios_seleccionados:
            funciones = [f for f in self.todas_las_funciones if f.__name__ in self.sitios_seleccionados]
        else:
            funciones = self.todas_las_funciones

        if not funciones:
            self.label_estado.configure(text="⚠️ No hay sitios para revisar", text_color="orange")
            return

        self.limpiar_resultados()
        self.btn_verificar.configure(state="disabled", text="Verificando...")
        self.label_estado.configure(
            text=f"Consultando {len(funciones)} plataforma(s) para {email}...",
            text_color="gray",
        )
        self.progress.start()

        import threading
        threading.Thread(target=self.ejecutar_verificacion, args=(email, funciones), daemon=True).start()

    def ejecutar_verificacion(self, email, funciones):
        try:
            resultados = trio.run(self._revisar_async, email, funciones)
        except Exception as e:
            self.after(0, lambda: self.mostrar_error_general(str(e)))
            return
        self.after(0, lambda: self.procesar_resultados(resultados, email))

    async def _revisar_async(self, email, funciones):
        resultados = []
        async with httpx.AsyncClient(timeout=15) as client:
            async with trio.open_nursery() as nursery:
                for funcion in funciones:
                    nursery.start_soon(self._ejecutar_modulo, funcion, email, client, resultados)
        return resultados

    @staticmethod
    async def _ejecutar_modulo(funcion, email, client, out):
        try:
            await funcion(email, client, out)
        except Exception:
            out.append({
                "name": funcion.__name__, "domain": funcion.__name__,
                "rateLimit": True, "exists": False,
                "emailrecovery": None, "phoneNumber": None, "others": None,
            })

    def procesar_resultados(self, resultados, email):
        if not self.mostrar_todo.get():
            resultados = [r for r in resultados if r.get("exists")]

        resultados = self.ordenar_resultados(resultados)

        for r in resultados:
            self.agregar_resultado(r)

        if not resultados:
            ctk.CTkLabel(
                self.frame_resultados, text="Sin resultados para mostrar con los filtros actuales",
                text_color="gray"
            ).pack(pady=10)

        self.progress.stop()
        self.btn_verificar.configure(state="normal", text="Verificar")
        self.label_estado.configure(
            text=(
                f"Listo — {self.contadores['encontrado']} encontrada(s) | "
                f"{self.contadores['rate_limit']} con límite | "
                f"correo: {email}"
            ),
            text_color="#1f8b4c",
        )

    def mostrar_error_general(self, mensaje):
        self.progress.stop()
        self.btn_verificar.configure(state="normal", text="Verificar")
        self.label_estado.configure(text=f"❌ Error: {mensaje}", text_color="red")


if __name__ == "__main__":
    app = VerificadorApp()
    app.mainloop()