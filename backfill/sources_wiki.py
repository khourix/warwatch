"""Wikipedia page views per theatre (Wikimedia pageviews API), daily from July 2015. Free, no key.

The article lists are fixed here before any view count was read (docs/WIKISTUDY_PLAN.md). Two series per theatre:
  wiki_<theatre>     summed daily views of the theatre's English articles
  wikiloc_<theatre>  summed daily views of its main country or conflict articles in the local languages
Only human traffic (agent=user), all platforms. Views follow the title: a page that was renamed keeps its older views under
the old title, so where a title is known to have moved both are listed. A title the API does not know is logged and skipped.
"""
import datetime as dt
import urllib.parse

import common as K

API = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{proj}/all-access/user/{title}/daily/{a}/{b}"
FLOOR = dt.date(2015, 7, 1)

EN = {
    "ukraine": ["Ukraine", "Russo-Ukrainian war", "Russo-Ukrainian War", "Russian invasion of Ukraine", "Armed Forces of Ukraine"],
    "europe_east": ["Suwałki Gap", "Kaliningrad Oblast", "Baltic states", "Lithuania", "Estonia", "Latvia", "Poland"],
    "iran": ["Iran", "Islamic Revolutionary Guard Corps", "Strait of Hormuz", "Nuclear program of Iran", "Ali Khamenei"],
    "yemen": ["Yemen", "Houthis", "Houthi movement", "Red Sea crisis", "Bab-el-Mandeb", "Yemeni civil war (2014–present)"],
    "israel": ["Israel", "Hezbollah", "Hamas", "Gaza Strip", "Israel Defense Forces", "West Bank"],
    "taiwan": ["Taiwan", "Taiwan Strait", "Cross-Strait relations", "People's Liberation Army", "Political status of Taiwan"],
    "scs": ["South China Sea", "Spratly Islands", "Second Thomas Shoal", "Scarborough Shoal", "Territorial disputes in the South China Sea"],
    "korea": ["North Korea", "Kim Jong Un", "Korean Demilitarized Zone", "Korean People's Army", "North Korea and weapons of mass destruction"],
    "southasia": ["Kashmir", "India–Pakistan relations", "Line of Control", "Pakistan Armed Forces", "Indian Armed Forces"],
    "libya": ["Libya", "Khalifa Haftar", "Libyan civil war (2014–2020)", "Tripoli", "Government of National Unity (Libya)"],
    "sudan": ["Sudan", "Rapid Support Forces", "Sudanese Armed Forces", "Sudanese civil war (2023–present)", "Darfur"],
    "drc": ["Democratic Republic of the Congo", "M23 campaign (2022–present)", "March 23 Movement", "North Kivu", "Goma"],
    "venezuela": ["Venezuela", "Nicolás Maduro", "Guayana Esequiba", "Venezuelan crisis", "Bolivarian Armed Forces of Venezuela"],
}
LOCAL = {
    "ukraine": [("uk.wikipedia", "Україна"), ("ru.wikipedia", "Украина")],
    "europe_east": [("pl.wikipedia", "Polska"), ("lt.wikipedia", "Lietuva"), ("ru.wikipedia", "Калининградская_область")],
    "iran": [("fa.wikipedia", "ایران"), ("he.wikipedia", "איראן")],
    "yemen": [("ar.wikipedia", "اليمن"), ("ar.wikipedia", "الحوثيون")],
    "israel": [("he.wikipedia", "ישראל"), ("ar.wikipedia", "حزب_الله"), ("he.wikipedia", "חזבאללה")],
    "taiwan": [("zh.wikipedia", "臺灣"), ("zh.wikipedia", "中華民國")],
    "scs": [("zh.wikipedia", "南海"), ("tl.wikipedia", "Dagat_Timog_Tsina")],
    "korea": [("ko.wikipedia", "조선민주주의인민공화국"), ("ko.wikipedia", "김정은")],
    "southasia": [("hi.wikipedia", "कश्मीर"), ("ur.wikipedia", "کشمیر")],
    "libya": [("ar.wikipedia", "ليبيا"), ("ar.wikipedia", "خليفة_حفتر")],
    "sudan": [("ar.wikipedia", "السودان"), ("ar.wikipedia", "قوات_الدعم_السريع")],
    "drc": [("fr.wikipedia", "République_démocratique_du_Congo"), ("fr.wikipedia", "Mouvement_du_23_mars")],
    "venezuela": [("es.wikipedia", "Venezuela"), ("es.wikipedia", "Nicolás_Maduro")],
}


def _views(proj, title, a, b):
    url = API.format(proj=proj, title=urllib.parse.quote(title.replace(" ", "_"), safe=""), a=a.strftime("%Y%m%d00"), b=b.strftime("%Y%m%d00"))
    try:
        js = K.get(url, retries=3)
    except Exception as e:
        K.log("skip", proj, title, str(e)[:80])
        return {}
    out = {}
    for it in js.get("items", []):
        d = f"{it['timestamp'][:4]}-{it['timestamp'][4:6]}-{it['timestamp'][6:8]}"
        out[d] = out.get(d, 0) + it["views"]
    K.log(proj, title, len(out), "days")
    return out


def cmd_wiki(start, end):
    a = max(start, FLOOR)
    for th in EN:
        for sid, arts in ((f"wiki_{th}", [("en.wikipedia", t) for t in EN[th]]), (f"wikiloc_{th}", LOCAL[th])):
            tot = {}
            for proj, t in arts:
                for d, v in _views(proj, t, a, end).items():
                    tot[d] = tot.get(d, 0) + v
            if tot:
                K.save(sid, sorted(tot.items()))
                K.log(sid, len(tot), "days", min(tot), "to", max(tot))
