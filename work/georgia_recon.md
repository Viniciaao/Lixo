# Georgia (MizuTS4) — reconhecimento de CCs

Reconhecimento recebido do usuário, originalmente realizado em **2026-09-06**.
Os commits locais `d1ddaec` e `d8e3d35` não vieram no checkout e não foram encontrados
no GitHub. Script, workflow e este mapeamento foram restaurados a partir do texto
fornecido pelo usuário — **não** são os commits originais recuperados.

## Retomada nesta sessão

- Branch fixo: `arena/01a078ab-lixo` (não o antigo `arena/01a07849-lixo`).
- O PR #2 de Helene já foi mesclado; Georgia terá um PR separado contra `main`.
- Workflow: `.github/workflows/fetch-georgia.yml`.
- Fetch: `scripts/fetch_georgia.py`; validação: `scripts/georgia_validation.py`.
- Resultados efetivos em `work/fetch_georgia_manifest.json` e
  `work/fetch_georgia_report.txt`, produzidos pelo runner, não por este documento.
- Downloads grandes ficam no artifact `georgia-tudo-junto` do Actions; o Git
  guarda manifestos, hashes, documentação e código, evitando novos blobs grandes.
- Não acessar contas, contornar assinatura/login ou usar mirrors não oficiais.

## O sim

- <https://www.curseforge.com/sims4/sims-households/georgia> — MizuTS4,
  “Sweet and dangerous.”
- `Georgia.zip`, file id **8674144**; reconhecimento informa 102,4 KB,
  upload em 2026-08-18, Alpha+1 / jogo 1.126.78. Esses metadados foram recebidos,
  não equivalem a teste no jogo; tamanho e hash reais constam no manifesto.
- Household/Tray, sem CC incluído.
- Rota pública: `/api/v1/mods/{modId}/files/8674144/download` no CurseForge,
  seguindo o redirecionamento fornecido pelo serviço.

## Mapeamento recebido (21 itens)

| # | Item | Criador | Fonte | Plano inicial |
|---|---|---|---|---|
| 01 | Sim Georgia | MizuTS4 | CurseForge 8674144 | AUTO |
| 02 | Hair S-Club 031226 Double Ponytail | S-Club | TSR 1766849 | MANUAL |
| 03 | Teeth “Normal”: Default alpha teeth all + Non-default | MagicBot | SFS folder 235489; Patreon 117517959 | AUTO; variantes |
| 04 | Fullbody Rina Sweatpants | Belaloallure (tabae) | TSR 1486209 | MANUAL |
| 05 | Leo levis shoes conversion, FIX F+M | MadMan / MagicBot | Patreon 23286338 | AUTO |
| 06 | GPME-GOLD MAKEUP SET CC31 | goppolsme | SFS 2172979 | AUTO |
| 07 | Basics Please: EyeLid / Full / OuterEdge | TwistedCat | Patreon 63321024 | AUTO |
| 08 | GPME-GOLD Liner cc10 | goppolsme | SFS 568017 | AUTO |
| 09 | WILD CAT: somente BLUSH N7 | Northern Siberia Winds | Patreon 64319245 | AUTO |
| 10 | Cytosine Eyes (facepaint) | RemusSirion | TSR 1459200 | MANUAL |
| 11 | Realistic Female Body Details | Mikooi / Miiko (confirmar autoria) | guia abaixo | MANUAL |
| 12 | misc. face details: TATTOO / OCCULT / SKINDETAIL | okruee | Patreon 71370172 | AUTO |
| 13 | Lighting Overlay 2.0: TRUE BLACK + COLOR | jo_se_oh | Patreon 94005453 | AUTO |
| 14 | In game shadow, 16 opções | Simandy | Patreon 42027501 | AUTO |
| 15 | Soft Face Freckles HQ | alf-si | TSR 1355997 | MANUAL |
| 16 | Bodycare Kit, seleção FEMALE / CLEAVAGE / BODY PRESET | Northern Siberia Winds | Patreon 93373994 | AUTO; excluir MALE |
| 17 | Tea Time Lashes HQ | venerian | TSR 1770164 | MANUAL |
| 18 | 3D Eyelashes Set: straight / curly / extra | obscurus | Patreon 93848968, indicado pelo post 93851178 | AUTO somente se público |
| 19 | Eyebrows 33–41 | alf-si / ANGISSI | Tumblr 614674051815849984; TSR 1561164/1561412/1561566 | MANUAL; mapeamento parcial |
| 20 | Cleavage Masks Collection | sims3melancholic | Drive folder 1p4W_kdF7oPJ4aRVQQ-alkEDZAJdrkm5B | AUTO |
| 21 | Nosemask N10 (70 cores) + overlay + 4 presets | obscurus | Patreon 26574490 | AUTO |

## Links e ressalvas do reconhecimento

- Sim: <https://www.curseforge.com/sims4/sims-households/georgia/files/8674144>.
- SFS: <https://simfileshare.net/download/2172979/>,
  <https://simfileshare.net/download/568017/>,
  <https://simfileshare.net/folder/235489/>.
- Drive: <https://drive.google.com/drive/folders/1p4W_kdF7oPJ4aRVQQ-alkEDZAJdrkm5B>.
- API pública Patreon: `/api/posts/{id}`. Sempre verificar
  `current_user_can_view` sem autenticação e usar nome/tamanho do próprio objeto
  `media`, associado pelo id. A ordem de `included` não garante a ordem do preview.
- Sobrancelhas: <https://alf-si.tumblr.com/post/614674051815849984>.
  Recebidos n33=1561164, n34=1561412, n35=1561566; **n36–41 não confirmados**.
- Body details: referência recebida
  <https://bestsimsmods.com/sims-4-mikkoi-female-body-details-6-0/>.
  O reconhecimento menciona conteúdo adulto, ~273 MB, requisito Get Famous e
  outra versão 8.8 em mirror. Autoria, versão e requisitos precisam ser confirmados
  pelo usuário com o criador; o mirror não será usado pelo fetch.
- MediaFire alternativo recebido para CC31: chave `0tnhzu2zrncobn5`;
  preferir SFS oficial mapeado. Nenhum mirror substitui automaticamente uma fonte.

## Critérios de conclusão

1. Enviar o branch **desta sessão**, disparar e acompanhar o workflow.
2. Registrar falhas reais (sem `exit 0` incondicional); itens bloqueados ficam manuais.
3. Rejeitar HTML/JSON/ponteiros LFS; validar DBPF 2.1 e limites do índice,
   CRC dos ZIP/RAR/7z, cabeçalhos DBPF internos e presença de Tray no sim.
4. Gerar SHA-256 dos downloads e membros dos arquivos compactados.
5. Montar README, links oficiais e pendências manuais, explicitando variantes,
   conflitos de defaults e ausência de teste no jogo.
6. Abrir PR novo; nunca chamar o pacote de “completo” enquanto houver itens manuais.

## Ajustes confirmados na retomada

A primeira execução (`34062492099`) validou 31 arquivos / 406.459.689 bytes,
mas falhou corretamente em três grupos. Não foi apresentada como pacote completo.

- **18:** <https://www.patreon.com/posts/93848968> anuncia atualização de
  2026-05-31 e remete a <https://www.patreon.com/posts/115736891>. A página
  de destino está marcada como bloqueada para visitantes anônimos, oferecendo
  participação **gratuita**. Agora é MANUAL (login/adesão gratuita), não uma
  afirmação de assinatura paga. Sem tentativa de baixar anexos protegidos.
- **21:** o post <https://www.patreon.com/posts/26574490> aponta explicitamente
  a <https://simfileshare.net/folder/66108/>. A pasta oferece **3** `.package`:
  nosemask N10 LRLE (`2802529`), overlay (`1041421`) e o pacote de presets 3f
  (`1041423`, contém as quatro opções, não quatro arquivos separados).
- **20:** a pasta raiz contém a subpasta `CLEAVAGE MASKS #1-6`
  (`1F9bkXOgfIReIMsnOBr7xQ3oC-Ti89D7K`), depois OVERLAYS / SKIN COLORS,
  depois SCARS / TATTOO. O fetch agora percorre somente essas subpastas públicas,
  com limites de profundidade/quantidade e detecção de ciclos.
- **14:** os 16 efeitos/opções estão em **3** arquivos (FaceMask, Skindetails,
  Tattoos), conforme os anexos efetivamente obtidos.
- **16:** o filtro encontrou **13 de 24** anexos; a seleção feminina excluiu os
  arquivos masculinos e não baixou o restante indiscriminadamente.
- **03:** os ZIPs são coleções DEFAULT/NON-DEFAULT. A coleção DEFAULT contém
  subpastas por expansão; a documentação alerta para selecionar variantes e
  packs possuídos, sem tratar tudo como dependência simultânea.

A sandbox conseguiu sincronizar metadados pelo Git, mas o host de armazenamento
Azure dos artifacts recusou a conexão (`EOF`). A validação binária completa é
executada no runner; não declarar que os binários foram verificados localmente.
O pacote completo de arquivos públicos deve ser obtido pelo artifact no navegador
ou por `gh run download` em uma máquina com acesso a esse armazenamento.

A segunda execução (`34062870040`) validou 55 arquivos / 502.465.421 bytes,
incluindo as **24 máscaras** do Drive. Restou somente o item 21: a API pública
agora entrega seu corpo em `content_json_string` (ProseMirror), com `content=null`.
O parser passou a ler os links desse formato também; isso não é conteúdo bloqueado.

A lista **original**, `Georgia/Georgia CC.txt`, foi extraída do ZIP validado como
`work/fetch_georgia_creator_cc.txt`. Ela confirma os URLs completos do TSR e os
posts originais de goppolsme (`44511936`, `19279776`), Simandy (Tumblr
`630272666330415104`) e sims3melancholic (`96600228`), agora registrados nas fontes.
Também revela duas ressalvas importantes:

- Item 04 é chamado de “Fullbody” e “[tabae]clothes01”, mas o link fornecido é
  **Belaloallure Rina Sweatpants**; confirmar a correspondência manualmente.
- Item 11 cita **Mikooi Sims**, `16154-realistic-female-body-details`, sem URL.
  Não assumir que seja Miiko ou que o guia/mirror recebido identifique a versão.

## Resultado final — 2026-09-06

- Workflow **success**: <https://github.com/Viniciaao/Lixo/actions/runs/34063244692>.
- **58 arquivos / 511.439.588 bytes (487,75 MiB)**: 54 `.package`, 3 ZIPs, 1 RAR.
- **13 grupos baixados, 8 manuais, zero falhas**. Manuais: 02, 04, 10, 11,
  15, 17, 18 e 19. Não equivale ao visual completo sem instalação manual.
- Validação binária no runner: DBPF 2.1/limites do índice, CRC, cabeçalhos
  internos, Tray e SHA-256; 81 membros internos catalogados nos arquivos compactados.
- As execuções bem-sucedidas `34063064401` e `34063244692` produziram as
  **mesmas 58 somas SHA-256 dos payloads**.
- **23 testes offline passaram**, assim como a conferência local de manifestos,
  documentação gerada, relatórios e `git diff --check`. Sem teste no jogo.
- README, `LINKS-ORIGINAIS.txt`, `INSTALACAO-MANUAL.txt`, `MANIFEST.json` e
  `SHA256SUMS.txt` estão em `georgia-tudo-junto/`. O artifact contém também `CCs/`.
- Download: <https://github.com/Viniciaao/Lixo/actions/runs/34063244692/artifacts/9998144878>.
  ZIP de 500.065.120 bytes; expiração informada pelo Actions: 2026-12-05T22:10:37Z.
  Faça cópia local antes da expiração; o ZIP do repositório não inclui esses binários.
- `work/georgia_delivery.json` guarda o id/digest/expiração do artifact e as
  verificações de entrega. O digest do ZIP é informado pelo Actions; o download
  desse ZIP não pôde ser repetido na sandbox devido ao bloqueio de rede já descrito.
- A cópia legível da lista do criador foi normalizada para LF; o ZIP original
  e seus hashes permanecem intocados.
