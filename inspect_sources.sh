#!/usr/bin/env bash
# Inspect download paths in depth (runs on GitHub Actions runner).
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
ACCEPT="text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"

echo "############ CURSEFORGE DOWNLOAD URLS ############"
cf_urls=(
  "https://www.curseforge.com/sims4/sims-households/helene-dacosta/download/8763744"
  "https://www.curseforge.com/sims4/create-a-sim/eggsims-earrings-19/download/6496196"
  "https://www.curseforge.com/sims4/create-a-sim/sparkly-french-nails/download/8649348"
  "https://www.curseforge.com/sims4/create-a-sim/shiny-patent-mary-jane-heels/download/7751173"
  "https://www.curseforge.com/sims4/create-a-sim/ava-sweatshirt/download/8177818"
)
for u in "${cf_urls[@]}"; do
  echo "### CF: $u"
  rm -f /tmp/h.txt /tmp/b.html /tmp/cj.txt
  curl -sSL -A "$UA" -H "Accept: $ACCEPT" -H "Accept-Language: en-US,en;q=0.9" --compressed -c /tmp/cj.txt -b /tmp/cj.txt \
       -D /tmp/h.txt -o /tmp/b.html -w "code=%{http_code} final=%{url_effective} type=%{content_type}\n" "$u" || echo "curl FAILED"
  grep -iE "^(HTTP|content-type|location|set-cookie)" /tmp/h.txt | head -6
  echo "body-size=$(wc -c < /tmp/b.html 2>/dev/null)"
  echo "--- forgecdn links in body:"
  grep -oE "https?://[a-z0-9.]*forgecdn\.net[^\"' <]*" /tmp/b.html 2>/dev/null | head -5
  echo "--- text markers:"
  grep -oiE "(adfree|ad-free|download[ -]?link|expired|invalid|seconds|captcha|cf-mitigated)" /tmp/b.html 2>/dev/null | sort | uniq -c | head -8
  echo
done

echo "############ PATREON (browser-like curl) ############"
pat_urls=(
  "https://www.patreon.com/posts/gpme-gold-c2-22436855"
  "https://www.patreon.com/posts/3d-eyelashes-123193524"
  "https://www.patreon.com/posts/gpme-gold-eyes-17490207"
  "https://www.patreon.com/posts/heather-skin-n7-85159474"
  "https://www.patreon.com/posts/belaloallure-day-77031948"
  "https://www.patreon.com/posts/wild-cat-make-up-64319245"
  "https://www.patreon.com/posts/helgatisha-sims-59616486"
  "https://www.patreon.com/posts/default-mouth-56990147"
)
for u in "${pat_urls[@]}"; do
  echo "### PATREON: $u"
  code=$(curl -sS -A "$UA" -H "Accept: $ACCEPT" -H "Accept-Language: en-US,en;q=0.9" --compressed -L \
        -o /tmp/p.html -w "%{http_code}" --max-time 30 "$u" 2>/dev/null || echo "curl_FAIL")
  echo "html code=$code size=$(wc -c < /tmp/p.html 2>/dev/null)"
  if [ "$code" = "200" ]; then
    grep -oiE "attachment|patron-only|pledge|unlock|subscribe|file\?h=" /tmp/p.html 2>/dev/null | sort | uniq -c | head -6
    grep -oE "https://www\.patreon\.com/file\?h=[^\"'&]*&i=[0-9]+" /tmp/p.html 2>/dev/null | head -3
  fi
  echo
done

echo "############ PATREON API ############"
for id in 22436855 123193524 17490207 85159474 77031948 64319245 59616486 56990147; do
  echo "### API post $id"
  curl -sS -A "$UA" -H "Accept: application/json, text/plain, */*" -o /tmp/api.json -w "api code=%{http_code} size=%{size_download}\n" --max-time 20 "https://www.patreon.com/api/posts/${id}" 2>/dev/null || echo "api FAIL"
  head -c 700 /tmp/api.json 2>/dev/null; echo; echo
done

echo "############ TISTORY / KAKAO ############"
curl -sS -A "$UA" -o /tmp/t.html -w "tistory code=%{http_code}\n" --max-time 30 "https://eunosims.tistory.com/entry/sims4cc-body-preset-1-5" 2>/dev/null || echo "tistory FAIL"
echo "--- package links:"
grep -oE "https://blog\.kakaocdn\.net/[^\"']*" /tmp/t.html 2>/dev/null | grep -iE "package|preset" | head -3
echo

echo "############ MEDIAFIRE API (kijiko) ############"
curl -sS -A "$UA" -o /tmp/mf.json -w "mf code=%{http_code}\n" --max-time 30 "https://www.mediafire.com/api/1.4/file/get.php?quick_key=tgp3kcs4iy2mnft&response_format=json" 2>/dev/null || echo "mf FAIL"
head -c 900 /tmp/mf.json 2>/dev/null; echo; echo

echo "############ SIMFILESHARE (kijiko) ############"
rm -f /tmp/cj.txt
curl -sSL -A "$UA" -H "Accept: $ACCEPT" --compressed -c /tmp/cj.txt -b /tmp/cj.txt \
     -o /tmp/sfs.html -w "sfs code=%{http_code} final=%{url_effective}\n" --max-time 40 "https://simfileshare.net/download/3247982/" 2>/dev/null || echo "sfs FAIL"
echo "--- forms/actions/download links:"
grep -oiE "(action|href)=\"[^\"]*\"" /tmp/sfs.html 2>/dev/null | grep -iE "download|submit|php" | head -10
grep -oiE "window\.location[^;]*|meta[^>]*refresh[^>]*" /tmp/sfs.html 2>/dev/null | head -5
echo
echo "############ DONE ############"
