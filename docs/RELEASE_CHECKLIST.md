# Release checklist

1. `pytest tests/ -q` en verde (dos pasadas consecutivas).
2. `python -m app.cli check` en verde; `python -m app.cli check --status` sin desajustes.
   Nota: `data/generated/questions.sqlite` queda fuera de la cobertura sha256 del
   manifest (la suite de tests lo ensucia); se verifica por esquema/centinelas,
   asi que el paso 1 ya no invalida el paso 2.
3. `CHANGELOG.md`: entrada nueva con la version y la fecha.
4. `pyproject.toml`: `version` subida.
5. `pwsh scripts/package.ps1` genera el zip; anotar `ARTIFACT` y `SHA256`.
6. Probar en carpeta limpia: `scripts/install.ps1`, luego
   `sistemes init && sistemes check && sistemes serve`.
7. `git tag v<version>` y push.
