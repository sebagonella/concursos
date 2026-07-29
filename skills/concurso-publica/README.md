# concurso-publica

Etapa 3: transforma a estrutura de um concurso no vault em **site estático** com mídias embutidas (podcast, mapa mental, vídeo, report) e quiz de flashcards. Uso local/rede doméstica; site só leitura (o vault é a fonte de verdade).

**Status: v0.2.0 — coletor + gerador de páginas + quiz implementados (20/20 testes).** Ver SKILL.md para o roadmap das entregas.

```bash
# coletar o modelo do site a partir de um concurso
python scripts/site_collector.py --concurso-dir <.../CONCURSOS/SEDES_2026> --out site-model.json
```

```bash
# gerar o site completo
python scripts/site_builder.py --concurso-dir <.../CONCURSOS/SEDES_2026> --out out/site
python -m http.server -d out/site 8000     # conferir localmente
```
Versão atual: **0.6.0** (site servido na raiz em `concursos.casa:8088`; leitura do padrão de pastas atual da `concurso-aprofunda`).
