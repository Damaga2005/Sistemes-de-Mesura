# F19 — Aplicación de escritorio para Windows

Empaqueta la app web existente como un `.exe` nativo de Windows. La capa de
escritorio es **puramente aditiva**: no reescribe la aplicación y el único
cambio de backend es una publicación de puerto opt-in en `web/server.py`.

## 1. Arquitectura

```
escritorio.py  (proceso principal, ventana pywebview)
   │
   ├─ lanza un hilo daemon ──► web.server.main(["--host","127.0.0.1","--port","0"])
   │                              │
   │                              ├─ ThreadingHTTPServer hace bind en 127.0.0.1:0
   │                              │   (el SO asigna un puerto libre real)
   │                              ├─ si $SM_PORT_FILE está definido: escribe el
   │                              │   puerto realmente enlazado en ese fichero (F19-00)
   │                              └─ serve_forever()
   │
   ├─ wait_for_port(): sondea el fichero hasta leer un puerto válido (timeout 15 s)
   ├─ wait_for_socket(): espera a que 127.0.0.1:<port> acepte conexión
   └─ webview.create_window(... "http://127.0.0.1:<port>/index.html")
      webview.start(debug=False)
```

No hay puente JS↔Python: el launcher **no** pasa `js_api` y arranca la
WebView con `debug=False`. La ventana solo carga una URL HTTP local; toda la
lógica sigue viviendo en `web/server.py` y `app/`, sin cambios salvo la
escritura de puerto descrita en §10.

## 2. Ejecución en desarrollo

```
python -m pip install -e ".[desktop]"
python escritorio.py
```

Arranca el servidor embebido en un puerto efímero y abre la ventana. No
requiere compilar nada.

## 3. Compilar el EXE

```
python -m pip install -e ".[desktop,build]"
.\build.ps1
```

Salida: `dist\SistemesDeMesura.exe` (un solo fichero, `console=False`, icono
`icono.ico`). `build.ps1` limpia `build\` y `dist\`, verifica que las
dependencias `webview` + `PyInstaller` estén presentes y valida que el exe
resultante no esté vacío. Equivalente manual:

```
python -m PyInstaller escritorio.spec --noconfirm --clean
```

## 4. Requisitos de Windows

- Windows 10 21H2 o superior, o Windows 11.
- **Microsoft Edge WebView2 Runtime** presente en el sistema. Viene de serie
  con Windows 11 y con las versiones actuales de Windows 10; si falta, hay que
  instalar el *Evergreen Runtime* desde Microsoft.
- F19 **no** empaqueta el bootstrapper Evergreen de WebView2 (decisión 6a): el
  instalador del runtime es responsabilidad del entorno, no del `.exe`.

## 5. Ubicación de datos

Estado escribible bajo `%LOCALAPPDATA%\SistemesDeMesura\`:

| Ruta | Contenido |
|---|---|
| `data\questions.sqlite` | copia semilla del banco de preguntas (se copia en el primer arranque) |
| `data\student.sqlite` | progreso del estudiante (mastery, sesiones, historial) |
| `backups\` | copias de seguridad |

Los artefactos empaquetados de solo lectura viajan dentro del directorio
temporal de PyInstaller (`_MEIxxxxxx`, expuesto como `sys._MEIPASS`) y nunca se
escriben: `app/paths.py::package_dir()` los resuelve ahí al estar congelado,
mientras `data_dir()` apunta a `%LOCALAPPDATA%`. Todas las rutas son
reconfigurables con `SM_HOME` (raíz) o los overrides por subdirectorio
(`SM_DATA_DIR`, `SM_BACKUP_DIR`, etc.).

## 6. Sin clave Gemini

Sin `GEMINI_API_KEY` en el entorno, el tutor usa el proveedor extractivo
determinista. El resto de la aplicación funciona igual y completamente
offline; no hay llamadas de red salvo las que haría Gemini si la clave
estuviera presente.

## 7. Solución de problemas de arranque

| Síntoma | Causa probable | Acción |
|---|---|---|
| "server did not publish its port within 15s" | antivirus bloqueando el proceso hijo, u otra instancia ya en marcha reteniendo recursos | cerrar la otra instancia; añadir excepción de antivirus para el `.exe` |
| Ventana en blanco o error al abrir la WebView | WebView2 Runtime ausente | instalar el Evergreen Runtime de Microsoft |
| El exe arranca pero no aparece ventana | el servidor no llegó a aceptar conexión en el puerto publicado | revisar logs, reintentar; comprobar que 127.0.0.1 no esté filtrado |

## 8. Limitaciones de CI

El job `desktop` (`windows-latest`) en `.github/workflows/ci.yml` valida
**solo el contrato de arranque / headless**:

- `pip install -e ".[dev,desktop,build]"` resuelve.
- La suite `pytest` pasa en Windows.
- `python -m app.cli init` + `check` pasan.
- PyInstaller construye `dist\SistemesDeMesura.exe`.
- El exe, lanzado con `SM_PORT_FILE` definido, publica su puerto y sirve
  `/index.html` y `/api/health` con HTTP 200.

**No** ejercita el render de WebView2, ni la interacción manual, ni la
transición de idioma F18-02. El job Linux `test` queda intacto; el job
`desktop` es independiente y aditivo.

## 9. Gate de runtime F18-02 (manual)

Checklist manual, no cubierto por CI:

1. Lanzar `SistemesDeMesura.exe`.
2. Inici → Exàmens → abrir o crear un examen.
3. Escribir una respuesta **sin guardar**.
4. Cambiar el idioma CA→ES con el selector de la cabecera.
5. Verificar que sobreviven, sin parpadeo de recarga: la respuesta escrita, la
   posición de la pregunta, el `?xsid=` de la sesión y el temporizador en marcha.
6. Repetir ES→CA.

Estado: **PASS** — ejecutado manualmente sobre el `.exe` real (build de
PyInstaller) el 2026-09-10. En el cambio CA→ES y de vuelta ES→CA sobreviven,
sin parpadeo de recarga, los cuatro elementos: la respuesta escrita sin
enviar, la posición/pregunta, el `?xsid=` de la sesión y el temporizador en
marcha.

Traza: la automatización con computer-use se intentó y quedó bloqueada (el
host no controla la ventana del `.exe`, y otra aplicación en primer plano
robaba el foco), por lo que la verificación se hizo a mano. CI **no** cubre
este gate (§8).

## 10. El carve-out `SM_PORT_FILE`

Único cambio de backend de todo F19. En `web/server.py::main()`, tras el
`bind` del `ThreadingHTTPServer` y antes de `serve_forever()`:

```python
_port_file = os.environ.get("SM_PORT_FILE")
if _port_file:
    try:
        Path(_port_file).write_text(str(srv.server_address[1]), encoding="utf-8")
    except OSError:
        pass
```

- Solo actúa si `SM_PORT_FILE` está definido en el entorno.
- Escribe el puerto **realmente enlazado** (`srv.server_address[1]`), que es lo
  que permite arrancar con `--port 0` y descubrir el puerto efímero.
- El `bind` del propio servidor es el único `bind`: no hay sonda
  `bind→close→rebind` ni ventana TOCTOU.
- Con la variable sin definir, el servidor es byte a byte idéntico al de antes
  de F19.
