# ContaIA – Guía de despliegue (sin instalar nada en tu computadora)

Todo se hace desde el navegador: GitHub (guarda el código), Railway (lo ejecuta) y AWS (Claude).

## 1. Subir el código a GitHub
1. Entra a github.com → **New repository** → nombre `contaia` → **Private** → *Create repository*.
2. En el repositorio vacío pulsa **uploading an existing file**.
3. Descomprime el ZIP en tu computadora y arrastra **todos los archivos** (app.py, db.py, paises.py, contabilidad.py,
   claude_bedrock.py, mock_claude.py, requirements.txt, railway.json, .gitignore) al navegador.
4. Pulsa **Commit changes**.

## 2. Crear el proyecto en Railway
1. En railway.com → **New Project → Deploy from GitHub repo** → elige `contaia`.
2. En el mismo proyecto: **+ New → Database → Add PostgreSQL**.
3. Entra al servicio de tu app (no al de la base) → pestaña **Variables** y agrega:

| Variable | Valor |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}`  (Railway lo completa solo) |
| `AWS_ACCESS_KEY_ID` | la clave de acceso del usuario IAM |
| `AWS_SECRET_ACCESS_KEY` | la clave secreta |
| `AWS_REGION` | `us-east-1` |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-haiku-5-5` |

4. Pestaña **Settings → Networking → Generate Domain**. Ese es el enlace de tu página.
5. Espera a que el despliegue termine (pestaña Deployments, en verde).

## 3. Probar
1. Abre el enlace → pantalla de bienvenida → completa tu empresa.
2. Ve a **Configuración → Probar conexión con AWS**. Debe decir "Conexión correcta".
   Si falla, el mensaje te dice qué revisar (permisos, modelo no habilitado, claves).
3. Ve a **Subir documentos**, sube una factura, revisa el asiento y pulsa **Registrar**.

## Cómo actualizar
Cambia un archivo en GitHub (botón de lápiz → Commit) y Railway vuelve a publicar solo.
Los datos no se pierden porque viven en PostgreSQL.

## Cómo agregar otro país
Abre `paises.py`, copia el bloque `PERU`, cambia plan de cuentas, tasas y reglas, y regístralo en `PAISES`.
Antes de habilitar un país verifica sus tasas y retenciones vigentes con un contador local.

## Notas
- Cada navegador queda ligado a su información mediante una cookie. En Configuración cada persona tiene su
  enlace de recuperación y un respaldo en Excel.
- El plan de cuentas es una versión simplificada del PCGE (cuentas de uso frecuente). Un contador debe revisar
  los asientos, sobre todo en detracciones, percepciones y activos fijos.
- Costo aproximado de Claude Haiku 5.5 en Bedrock: unos US$0.10 por millón de tokens de entrada (documentos pequeños);
  confirma precios en la página de Amazon Bedrock.
