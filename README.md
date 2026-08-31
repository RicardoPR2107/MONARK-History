# Verificador de Cuentas por Email (OSINT)

Aplicación de escritorio con interfaz gráfica (Python + CustomTkinter) que usa la librería [Holehe](https://github.com/megadose/holehe) para revisar en qué plataformas (~120 sitios: GitHub, Spotify, Discord, Adobe, Amazon, etc.) está registrado un correo electrónico.

Holehe funciona consultando el formulario público de **"olvidé mi contraseña"** o de registro de cada sitio y observando la respuesta. **No envía correos ni notifica a nadie** — es una técnica pasiva de OSINT (*Open Source Intelligence*: recolección de información a partir de fuentes públicas).

## ⚠️ Aviso legal y ético

Esta herramienta está pensada para que **verifiques tus propios correos** (por ejemplo, para saber en qué cuentas olvidadas sigue activo un correo que quieres dar de baja, o para revisar exposición ante filtraciones). Úsala únicamente sobre correos de tu propiedad o con autorización explícita del titular. El autor no se hace responsable del uso indebido de este software.

## Características

- Interfaz gráfica con CustomTkinter (no requiere usar la terminal para operarlo, solo para instalarlo).
- Revisión de las ~120 plataformas soportadas por Holehe, o de sitios específicos mediante un buscador con autocompletado.
- Filtro para mostrar solo las cuentas encontradas o también las no encontradas.
- Ordenamiento de resultados por nombre (A-Z / Z-A) o por fecha de creación de cuenta cuando el sitio la expone (actualmente solo ProtonMail entrega esa fecha; el resto de sitios no la exponen por diseño de sus propias APIs).
- Ejecución en segundo plano (hilo separado) para que la interfaz no se congele mientras se consultan los sitios.

## Requisitos

- Python 3.9 o superior
- pip

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/RicardoPR2107/MONARK-History.git
cd verificador-cuentas-osint

# 2. Crear un entorno virtual
python -m venv venv

# 3. Activar el entorno virtual
# En Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# En Linux / macOS:
source venv/bin/activate

# 4. Instalar las dependencias
pip install -r requirements.txt
```

> `trio` y `httpx` se instalan automáticamente como dependencias de Holehe, no hace falta agregarlos aparte.

## Uso

Con el entorno virtual activado:

```bash
python verificador_cuentas.py
```

1. Escribe el correo a verificar y presiona **Verificar** (o Enter) para revisar todas las plataformas soportadas.
2. Opcionalmente, escribe en el campo de búsqueda de sitios (ej. `git`, `spot`) para que aparezcan sugerencias y selecciones solo esos sitios específicos.
3. Activa la casilla "Mostrar también los NO registrados" si quieres ver el listado completo, no solo las coincidencias.
4. Cambia el criterio de "Ordenar por" según necesites.

## Solución de problemas comunes

- **"No se encontró 'holehe'"**: asegúrate de haber activado el entorno virtual (`venv`) antes de instalar dependencias y antes de correr el script. Debes ver `(venv)` al inicio de tu terminal.
- **Resultados con "⏱️ rate limit"**: la plataforma consultada bloqueó temporalmente las solicitudes desde tu IP por exceso de peticiones. Espera unos minutos o cambia de red, no es un error del script.
- **Error de política de ejecución en PowerShell** al activar el venv: corre una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Créditos

- [Holehe](https://github.com/megadose/holehe) de Megadose — motor de verificación OSINT.
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — librería de interfaz gráfica.

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.
