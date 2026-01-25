import requests

# for example
#url = 'https://ekaterinburg.hh.ru/resume/b55635f000075c6ae900bfb7af6b7632343631?query=%D0%90%D0%BD%D0%B0%D0%BB%D0%B8%D1%82%D0%B8%D0%BA+%D0%B4%D0%B0%D0%BD%D0%BD%D1%8B%D1%85+%28Data+Analyst%29&searchRid=176919267493439f5b4f31a807cf3026&hhtmFrom=resume_search_result'

def get_html(url):
    response = requests.get(
                            url
                            #,headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; rv:121.0) Gecko/20100101 Firefox/121.0'}
                            ,headers={'User-Agent': 'Chrome/121.0 DEIC-M2-Win7-INTQZ.DEI#415 (Windows NT 10.0.11621.0; rv:121.0) Gecko/20120301 Firefox/121.0',}
                            )
    if response.status_code != 200:
        return
    return response.text

#print(get_html(url))
