#!/usr/bin/env python3
"""Render Georgia's documentation from its measured manifest; optionally revalidate payloads."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from georgia_validation import safe_member, validate_file

PACK = Path("georgia-tudo-junto")


def check_manifest(manifest):
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema")
    items = manifest["items"]
    if [item["id"] for item in items] != [f"{i:02}" for i in range(1, 22)]:
        raise ValueError("manifest must contain the 21 mapped items, in order")
    files = []
    for item in items:
        if item["status"] not in {"downloaded", "manual", "failed"}:
            raise ValueError("unresolved source status")
        if item["status"] == "downloaded" and not item["files"]:
            raise ValueError("downloaded source without files")
        if item["status"] == "manual" and item["files"]:
            raise ValueError("manual source must not silently include files")
        for record in item["files"]:
            safe_member(record["path"])
            path = Path(record["path"])
            if len(path.parts) != 2 or path.parts[0] != "CCs" or not path.name.startswith(item["id"] + "_"):
                raise ValueError("file path does not belong to its source")
            if not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]):
                raise ValueError("invalid SHA-256")
            if not isinstance(record["bytes"], int) or record["bytes"] <= 0:
                raise ValueError("invalid payload size")
            if record["format"] not in {"package", "zip", "rar", "7z"} or path.suffix != "." + record["format"]:
                raise ValueError("file format/path mismatch")
            files.append(record)
    if len({f["path"].casefold() for f in files}) != len(files):
        raise ValueError("duplicate payload paths")
    expected = {"files": len(files), "bytes": sum(f["bytes"] for f in files),
                **{s: sum(i["status"] == s for i in items) for s in ("downloaded", "manual", "failed")}}
    if manifest["summary"] != expected:
        raise ValueError("manifest summary disagrees with its records")
    return sorted(files, key=lambda f: f["path"])


def checksums(files):
    return "".join(f"{f['sha256']}  {f['path']}\n" for f in files)


def render(manifest):
    files = check_manifest(manifest)
    summary, items = manifest["summary"], manifest["items"]
    incomplete = summary["manual"] + summary["failed"]
    statuses = {"downloaded": "Validado", "manual": "Manual — não incluído", "failed": "Falhou / incompleto"}
    rows = ["| # | Item / criador | Situação | Arquivos |", "|---|---|---|---:|"]
    for item in items:
        rows.append(f"| {item['id']} | {item['name']} — {item['creator']} | {statuses[item['status']]} | {len(item['files'])} |")
    run_url = manifest.get("workflow_run")
    download = "Este manifesto foi gerado localmente. Os arquivos ficam em `CCs/`."
    if run_url:
        run_id = run_url.rstrip("/").rsplit("/", 1)[-1]
        if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/[0-9]+", run_url):
            raise ValueError("invalid workflow URL")
        repository = "/".join(run_url.split("/")[3:5])
        download = f"""1. Abra [a execução que produziu estes arquivos]({run_url}).
2. Confira o resultado **success**. Em **Artifacts**, baixe **georgia-tudo-junto**
   (o GitHub pode exigir login).
3. Extraia o artifact para uma pasta `georgia-tudo-junto/` e confira os hashes
   **antes de instalar**. Um artifact de execução falha pode estar parcial.

Alternativa com GitHub CLI:

```bash
gh run download {run_id} --repo {repository} \\
  --name georgia-tudo-junto --dir georgia-tudo-junto
```

**Armazenamento:** os binários não estão em blobs Git nem em ponteiros Git LFS de
Georgia: ficam no artifact do Actions. A retenção solicitada é **90 dias**, sujeita
às políticas/remoção do repositório. Faça uma cópia local. O botão *Download ZIP*
do repositório contém a documentação e os scripts, **não os CCs de Georgia**.
Se o artifact expirar, execute o fetch novamente; a disponibilidade e os hashes
podem mudar nas fontes originais."""
    readme = f"""# Georgia (MizuTS4) — Sim + CCs públicos

> **Não é o visual completo instalado automaticamente.** {incomplete} dos 21 itens
> mapeados dependem de download manual ou resolução de pendências. As variantes
> reunidas também precisam ser escolhidas antes de instalar.

Sim: [Georgia — “Sweet and dangerous.”](https://www.curseforge.com/sims4/sims-households/georgia),
por **MizuTS4**, arquivo CurseForge **8674144** (`Georgia.zip`). O ZIP do sim
contém o household/Tray; os CCs são arquivos separados dos respectivos criadores.

## Resultado medido

- **{summary['files']} arquivos**, **{summary['bytes']:,} bytes** ({summary['bytes'] / 1024**2:.2f} MiB).
- **{summary['downloaded']} grupos baixados/validados**, **{summary['manual']} manuais**,
  **{summary['failed']} com falha**. Um grupo pode conter várias alternativas.
- Manifesto gerado em **{manifest['generated_at']}** (UTC).
- Código usado: `{manifest['checkout_sha']}`.
- `MANIFEST.json` relaciona cada arquivo à fonte, tamanho, SHA-256, formato e
  membros internos; `SHA256SUMS.txt` cobre todos os binários distribuídos.

## Obter a pasta com os arquivos

{download}

## Conteúdo da pasta

```text
georgia-tudo-junto/
├── README.md
├── LINKS-ORIGINAIS.txt
├── INSTALACAO-MANUAL.txt
├── MANIFEST.json
├── SHA256SUMS.txt
└── CCs/                     # presente no artifact; ignorado pelo Git
    ├── 01_SIM-Georgia.zip
    └── demais .package / .zip / .rar / .7z validados
```

## Instalação segura

1. Faça backup de `Documentos/Electronic Arts/The Sims 4/` e confira se já usa
   algum dos mesmos CCs/defaults. **Não copie a pasta `CCs/` inteira para Mods.**
2. Extraia `CCs/01_SIM-Georgia.zip`. Os arquivos do household
   (`.trayitem`, `.householdbinary`, `.hhi`, `.sgi`) vão diretamente em
   `Documentos/Electronic Arts/The Sims 4/Tray/`, sem subpastas.
   Imagens/textos auxiliares não vão para Tray.
3. Para os CCs, extraia os demais ZIP/RAR/7z com um descompactador compatível.
   Copie somente os **`.package` escolhidos** para
   `Documentos/Electronic Arts/The Sims 4/Mods/Georgia/`.
   O jogo não lê os CCs dentro dos arquivos compactados.
4. Complete os itens de `INSTALACAO-MANUAL.txt` pelas páginas dos criadores.
   Respeite login, assinatura, requisitos HQ/expansões e instruções da versão
   selecionada; este pacote não contorna essas condições.
5. No jogo, ative **Conteúdo personalizado e modificações** em Opções → Outros
   e reinicie. Os arquivos reunidos não exigem habilitar *mods de script*.
6. Na Galeria → Minha Biblioteca, habilite o filtro **Incluir conteúdo
   personalizado** e procure Georgia. Sem os itens manuais, sua aparência pode
   diferir da imagem do criador.

### Variantes e possíveis conflitos

- **03 (dentes):** foram reunidas opções DEFAULT e NON-DEFAULT. Um default
  substitui conteúdo global do jogo; não instale defaults concorrentes de dentes.
  Escolha conforme as instruções de MagicBot e os defaults já instalados. O ZIP
  DEFAULT também separa opções por expansão (Get Famous, Growing Together,
  Island Living, Vampires, Werewolves); não instale opções de packs que não possui.
  Para “Normal”, confira as opções `teeth base` com o criador — o reconhecimento
  não confirma qual versão DEFAULT/NON-DEFAULT foi usada no household.
- **07 (eyeshadow), 12 (face details), 13 (lighting), 14 (shadow):** há versões,
  categorias e/ou opções visuais. Não são todas dependências simultâneas.
- **16 (Bodycare), 20 (cleavage masks), 21 (nosemask/presets):** escolha máscaras,
  overlays e presets adequados no CAS. Não aplique todos ao mesmo tempo.
- Confira também as variantes de cílios, HQ/non-HQ e possíveis conflitos de slots
  com acessórios. Não há garantia de compatibilidade entre todos os CCs.
- O reconhecimento não determinou todas as variantes exatas usadas por MizuTS4;
  por exemplo, as sobrancelhas 33–41 ainda têm mapeamento parcial.

## Status por item

{chr(10).join(rows)}

Veja as páginas originais e os downloads públicos resolvidos em
`LINKS-ORIGINAIS.txt`; os itens ausentes e suas ressalvas estão em
`INSTALACAO-MANUAL.txt`.

## Verificar integridade

Linux/WSL (a partir da raiz do checkout, após obter o artifact):

```bash
cd georgia-tudo-junto
sha256sum -c SHA256SUMS.txt
```

No PowerShell, dentro de `georgia-tudo-junto/`:

```powershell
Get-Content SHA256SUMS.txt | ForEach-Object {{
  $hash, $file = $_ -split '  ', 2
  if ((Get-FileHash -LiteralPath $file -Algorithm SHA256 -ErrorAction Stop).Hash -ine $hash) {{
    throw "SHA-256 incorreto: $file"
  }}
  "OK: $file"
}}
```

A validação automatizada rejeita HTML/JSON e ponteiros LFS; confere assinatura
DBPF 2.1, cabeçalho/limites do índice, CRC dos arquivos compactados, cabeçalhos
DBPF internos e presença dos arquivos essenciais do household. Os hashes dos
membros internos constam no manifesto. **Isso não é uma análise antivírus nem
um teste no jogo**: integridade estrutural não comprova compatibilidade ou
reproduz exatamente a aparência do sim. O jogo não foi executado nesta sessão.

## Reproduzir / manter

Na raiz do repositório, com Python 3.11+ e 7-Zip (`7z` ou `7zz`) no PATH:

```bash
python -m pip install -r scripts/requirements-georgia.txt
python -m unittest discover -s tests -v
# CCs/ precisa estar vazia; mova uma cópia antiga para outro lugar, se existir.
python scripts/fetch_georgia.py
python scripts/package_georgia.py --verify
```

O fetch usa somente endpoints públicos e não precisa de chaves Patreon/CurseForge.
Se um post passar a exigir acesso, ele fica manual. Falhas HTTP/de validação
produzem código de saída diferente de zero, nunca sucesso artificial.
O workflow `fetch-georgia.yml` também pode ser executado no branch
`arena/01a078ab-lixo` enquanto ele existir. Revisar os relatórios quando as fontes
mudarem; os checksums são um retrato desta execução, não assinaturas dos autores.

## Créditos e direitos

Cada CC pertence ao criador identificado acima. Este agrupamento não altera as
licenças/termos desses arquivos: a licença do código do repositório **não licencia
os CCs de terceiros**. Acesso público não equivale a permissão de redistribuição;
respeite os termos de cada criador e prefira compartilhar seus links originais.
O item adulto 11 não foi baixado nem validado; sua referência é apenas uma pista
fornecida no reconhecimento, não confirmação de autoria/versão/requisitos.
"""
    links = ["GEORGIA — FONTES E CRÉDITOS", "", "URLs sem tokens temporários. Item 11: referência recebida, não fonte autoral confirmada.", ""]
    manual = ["GEORGIA — DOWNLOADS MANUAIS / PENDÊNCIAS", "", "Estes itens NÃO estão completos na pasta CCs. Não contornar login/assinatura.", ""]
    for item in items:
        heading = f"{item['id']} — {item['name']} | {item['creator']}"
        urls = list(dict.fromkeys(item["urls"] + [f["source_url"] for f in item["files"]]))
        links.extend([heading, *urls, item["note"], ""])
        if item["status"] != "downloaded":
            manual.extend([heading, f"Situação: {statuses[item['status']]}", item["note"],
                           *item.get("errors", []), *item["urls"], ""])
    manual.extend(["Não foi testado no jogo. Sem os itens manuais, a aparência de Georgia pode diferir.",
                   "Escolha variantes/defaults compatíveis; não instale tudo indiscriminadamente.", ""])
    return {"README.md": readme, "LINKS-ORIGINAIS.txt": "\n".join(links).rstrip() + "\n",
            "INSTALACAO-MANUAL.txt": "\n".join(manual), "SHA256SUMS.txt": checksums(files)}


def verify_payloads(pack, manifest):
    files = check_manifest(manifest)
    expected = {f["path"] for f in files}
    actual = {p.relative_to(pack).as_posix() for p in (pack / "CCs").rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError(f"payload set mismatch: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}")
    for record in files:
        path = pack / record["path"]
        if path.is_symlink():
            raise ValueError("payload must not be a symlink")
        result = validate_file(path, household=path.name.startswith("01_"))
        for field in ("bytes", "sha256", "format", "members"):
            if result[field] != record[field]:
                raise ValueError(f"{field} mismatch for {path}")
        print(f"OK {record['path']} {record['sha256']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=PACK)
    parser.add_argument("--verify", action="store_true", help="revalidate every binary against the manifest")
    parser.add_argument("--check-metadata", action="store_true", help="check tracked documentation without downloads")
    args = parser.parse_args()
    manifest = json.loads((args.pack / "MANIFEST.json").read_text(encoding="utf-8"))
    documents = render(manifest)
    if args.verify:
        verify_payloads(args.pack, manifest)
    if args.check_metadata:
        for name, expected in documents.items():
            if (args.pack / name).read_text(encoding="utf-8") != expected:
                raise ValueError(f"stale documentation/checksums: {name}")
        print("Metadata, summary, source coverage, documentation and checksums: OK")
    else:
        for name, contents in documents.items():
            (args.pack / name).write_text(contents, encoding="utf-8")
        print("Rendered README, original links, manual instructions and SHA256SUMS.")
    return 1 if manifest["summary"]["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
