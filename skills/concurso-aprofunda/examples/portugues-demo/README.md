# Exemplo — Português

Arquivos de exemplo para exercitar a skill sem um livro real:

- `assuntos-exemplo.json` — lista de assuntos mapeados (entrada do book_index.py)
- `mapa-localizacao-exemplo.json` — saída do book_index.py (onde cada assunto está no livro)

Para reproduzir o fluxo, gere um PDF de teste ou use um livro real e rode:

```bash
python ../../scripts/book_index.py --livro <seu-livro.pdf> --assuntos assuntos-exemplo.json --out mapa.json
python ../../scripts/build_subject_md.py --mapa mapa.json --out-dir assuntos/ --concurso SEDES_2026
```
