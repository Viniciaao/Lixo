# Georgia (MizuTS4) — Sim + CCs públicos

> **Não é o visual completo instalado automaticamente.** 8 dos 21 itens
> mapeados dependem de download manual ou resolução de pendências. As variantes
> reunidas também precisam ser escolhidas antes de instalar.

Sim: [Georgia — “Sweet and dangerous.”](https://www.curseforge.com/sims4/sims-households/georgia),
por **MizuTS4**, arquivo CurseForge **8674144** (`Georgia.zip`). O ZIP do sim
contém o household/Tray; os CCs são arquivos separados dos respectivos criadores.

## Resultado medido

- **58 arquivos**, **511,439,588 bytes** (487.75 MiB).
- **13 grupos baixados/validados**, **8 manuais**,
  **0 com falha**. Um grupo pode conter várias alternativas.
- Manifesto gerado em **2026-09-06T22:11:43.968793+00:00** (UTC).
- Código usado: `1d90e6b25410efb2b740bc868c64926840469e69`.
- `MANIFEST.json` relaciona cada arquivo à fonte, tamanho, SHA-256, formato e
  membros internos; `SHA256SUMS.txt` cobre todos os binários distribuídos.

## Obter a pasta com os arquivos

1. Abra [a execução que produziu estes arquivos](https://github.com/Viniciaao/Lixo/actions/runs/34063244692).
2. Confira o resultado **success**. Em **Artifacts**, baixe **georgia-tudo-junto**
   (o GitHub pode exigir login).
3. Extraia o artifact para uma pasta `georgia-tudo-junto/` e confira os hashes
   **antes de instalar**. Um artifact de execução falha pode estar parcial.

Alternativa com GitHub CLI:

```bash
gh run download 34063244692 --repo Viniciaao/Lixo \
  --name georgia-tudo-junto --dir georgia-tudo-junto
```

**Armazenamento:** os binários não estão em blobs Git nem em ponteiros Git LFS de
Georgia: ficam no artifact do Actions. A retenção solicitada é **90 dias**, sujeita
às políticas/remoção do repositório. Faça uma cópia local. O botão *Download ZIP*
do repositório contém a documentação e os scripts, **não os CCs de Georgia**.
Se o artifact expirar, execute o fetch novamente; a disponibilidade e os hashes
podem mudar nas fontes originais.

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

| # | Item / criador | Situação | Arquivos |
|---|---|---|---:|
| 01 | Sim Georgia — MizuTS4 | Validado | 1 |
| 02 | Hair S-Club 031226 Double Ponytail — S-Club | Manual — não incluído | 0 |
| 03 | Teeth "Normal" — alpha teeth — MagicBot | Validado | 2 |
| 04 | Rina Sweatpants (Fullbody na lista do sim) — Belaloallure; lista cita [tabae]clothes01 | Manual — não incluído | 0 |
| 05 | Leo levis shoes conversion — MadMan / MagicBot | Validado | 1 |
| 06 | GPME-GOLD MAKEUP SET CC31 — goppolsme | Validado | 1 |
| 07 | Basics Please — eyeshadows — TwistedCat | Validado | 3 |
| 08 | GPME-GOLD Liner cc10 — goppolsme | Validado | 1 |
| 09 | WILD CAT — BLUSH N7 — Northern Siberia Winds | Validado | 1 |
| 10 | Cytosine Eyes — facepaint — RemusSirion | Manual — não incluído | 0 |
| 11 | Realistic Female Body Details (16154) — Mikooi Sims (conforme lista do sim) | Manual — não incluído | 0 |
| 12 | misc. face details — okruee | Validado | 3 |
| 13 | Lighting Overlay 2.0 — jo_se_oh | Validado | 2 |
| 14 | In game shadow — face shadow — Simandy | Validado | 3 |
| 15 | Soft Face Freckles HQ — alf-si | Manual — não incluído | 0 |
| 16 | Bodycare Kit — seleção feminina — Northern Siberia Winds | Validado | 13 |
| 17 | Tea Time Lashes HQ — venerian | Manual — não incluído | 0 |
| 18 | 3D Eyelashes Set — obscurus | Manual — não incluído | 0 |
| 19 | Eyebrows 33–41 — alf-si / ANGISSI | Manual — não incluído | 0 |
| 20 | Cleavage Masks Collection — sims3melancholic | Validado | 24 |
| 21 | Nosemask N10 + overlay + presets — obscurus | Validado | 3 |

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
Get-Content SHA256SUMS.txt | ForEach-Object {
  $hash, $file = $_ -split '  ', 2
  if ((Get-FileHash -LiteralPath $file -Algorithm SHA256 -ErrorAction Stop).Hash -ine $hash) {
    throw "SHA-256 incorreto: $file"
  }
  "OK: $file"
}
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
