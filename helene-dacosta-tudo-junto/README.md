# 🎀 Helene Dacosta — Pacote Completo (Sim + CCs)

Pacote reunindo o sim **Helene Dacosta** (by Danielavlp, CurseForge) e **todos os
arquivos de Custom Content (CC)** listados na descrição original do sim, para você
instalar tudo de uma vez.

> **Aviso importante de uso**
> Todos os CC pertencem aos seus criadores originais. Este repositório é um
> *agrupador para uso pessoal*: o conteúdo foi baixado dos links oficiais de cada
> criador. Não redistribua os arquivos; compartilhe apontando para este repositório
> e para as páginas originais (lista em `LINKS-ORIGINAIS.txt`).

---

## 📁 O que tem aqui

```
helene-dacosta-tudo-junto/
├── README.md                  ← você está aqui
├── LINKS-ORIGINAIS.txt        ← todas as páginas oficiais de cada item
├── INSTALACAO-MANUAL.txt      ← itens que precisam de download manual (login)
├── SHA256SUMS.txt             ← checagem de integridade dos arquivos
└── CCs/                       ← os arquivos prontos para instalar
    ├── 01_SIM-Helene-Dacosta.zip   (tray → pasta Tray/)
    ├── 02_EGGSIMS-earrings-19.zip
    ├── 03_Sparkly-French-Nails.zip
    ├── 04_Shiny-Patent-Mary-Jane-Heels.zip
    ├── 05_Ava-Sweatshirt.zip
    ├── 07_Belaloallure-...        (Patreon → .package)
    ├── 08_GPME-Gold-C2-contour.package
    ├── 09_GPME-Gold-Eyes-G2.package
    ├── 11_NSW-LIPS-N35_...package
    ├── 12_obscurus-lips-presets-7f.package
    ├── 13_MagicBot-Default-Mouth.package
    ├── 14_Kijiko-Remove-EA-Lashes.zip
    └── 15_eunosims-euno-Body-preset.package
```

Itens **06, 10, 16–21** estão pendentes (ver seção de status) — o 06 pode entrar
via Git LFS após nova execução do workflow de fetch.

---

## 🚀 Como instalar

1. **Os `.package`** → copie para:
   `Documentos/Electronic Arts/The Sims 4/Mods/`
   (pode criar subpastas, ex.: `Mods/HeleneDacosta/`)

2. **Os `.zip`** → extraia e coloque o conteúdo dentro de `Mods/`.

3. **O sim em si** (`01_...zip` da Helene, formato .tray) → extraia o conteúdo
   (`*.trayitem` / `*.blueprint` / `*.bpi`) para:
   `Documentos/Electronic Arts/The Sims 4/Tray/`

4. No jogo: ative Mods personalizados e *Script Mods* em
   **Opções → Outros**, reinicie o jogo, e procure a Helene na **Galeria**
   (filtro "Minha Biblioteca") para colocá-la no mundo.

> Os CCs de **pele/olhos/cílios/corpo** são *defaults ou presets* que funcionam
> automaticamente assim que o sim usa a roupa/maquiagem do visual dela.

---

## 📋 Itens usados pelo sim (lista completa)

| # | Item | Criador | Host | Status |
|---|------|---------|------|--------|
| 01 | Helene Dacosta (o sim/household) | Danielavlp | CurseForge | ✅ baixado (tray) |
| 02 | [EGGSIMS] earrings 19 | eggu_sims | CurseForge | ✅ baixado |
| 03 | Sparkly French Nails | 4w25 | CurseForge | ✅ baixado |
| 04 | Shiny Patent Mary Jane Heels | PolySphere | CurseForge | ✅ baixado |
| 05 | Ava Sweatshirt | MissValentinee | CurseForge | ✅ baixado |
| 06 | Heather Skin (Skin N7) | poyopoyosim | Google Drive/Patreon | ⚠️ arquivo grande (ver abaixo) |
| 07 | `_phaedra_mini_skirt` | Belaloallure | Patreon | ✅ baixado |
| 08 | GPME Gold C2 (contour) | goppolsme | Patreon/SimFileShare | ✅ baixado |
| 09 | GPME Gold Eyes G2 | goppolsme | Patreon/SimFileShare | ✅ baixado |
| 10 | 3D Eyelashes N6 | Northern Siberia Winds | Patreon | 🔒 atrás de assinatura |
| 11 | LIPS N35 (Wild Cat Make-up) | Northern Siberia Winds | Patreon | ✅ baixado |
| 12 | `_lips_presets_7f` (helgatisha) | obscurus-sims | Patreon/SimFileShare | ✅ baixado |
| 13 | Default Mouth | MagicBot | Patreon/SimFileShare | ✅ baixado |
| 14 | EA Eyelashes Remover | Kijiko | kijiko-catfood.com | ✅ baixado |
| 15 | Body preset (eunosims) | eunosims | tistory | ✅ baixado |
| 16 | Holiday Snow Blush | VELYSEA | The Sims Resource | 🔒 manual (login) |
| 17 | Eyeshadow N42 | (TSR) | The Sims Resource | 🔒 manual (login) |
| 18 | Elegante Long Hairstyle 071124 | S-CLUB | The Sims Resource | 🔒 manual (login) |
| 19 | Eyebrows 28 v2 | (TSR) | The Sims Resource | 🔒 manual (login) |
| 20 | S-CLUB WM TS4 Eyelashes 201801 | S-CLUB | The Sims Resource | 🔒 manual (login) |
| 21 | Freckles Z53 | (TSR) | The Sims Resource | 🔒 manual (login) |

Legenda: ✅ baixado · ⏳ download automático pendente · 🔒 download manual necessário

---

## ⚠️ Item 06 — Heather Skin (365 MB)

O arquivo da pele tem **~365 MB** e o GitHub não aceita arquivos acima de 100 MB
em repositórios comuns. Decisão em andamento:

- **Opção A (Git LFS):** o arquivo entra no repositório via Git LFS — o workflow
  de fetch já está configurado para rastrear `CCs/06_*` com LFS (o arquivo fica
  disponível após a próxima execução). Para baixá-lo pelo `git clone`/`git pull`
  você precisa ter `git lfs install` feito uma vez na sua máquina.
- **Opção B (link direto):** link do Google Drive dela dentro deste README.

Download direto (se precisar agora):
<https://drive.usercontent.google.com/download?id=1O4qRheU3lpua7WBt5rbv6Waz2fIwdwrX&export=download&confirm=t>

---

## 🔒 Itens que exigem download manual

`INSTALACAO-MANUAL.txt` tem o passo a passo + links exatos de cada um:
- 6 itens do **The Sims Resource** (conta gratuita necessária)
- **NSW 3D Eyelashes N6** (assinatura no Patreon do criador)

---

*Pacote montado em 2026-09-06 · arquivos verificados (hash SHA-256) em `SHA256SUMS.txt`.*
