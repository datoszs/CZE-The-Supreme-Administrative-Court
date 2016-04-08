#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# coding=utf-8

import requests
import re
import json
import os
import time
import logging
import pprint
import codecs
import sys

# nastaveni logovani
logger = logging.getLogger("%(file)s")
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler("ocr_prevod_log.txt",mode="w",encoding='utf-8')
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
# add the handlers to logger
logger.addHandler(ch)
logger.addHandler(fh)

out_dir = "output_data"
json_dir = "JSON"
txt_dir = "TXT"
txt_dir_path = os.path.join(out_dir,txt_dir)
json_dir_path = os.path.join(out_dir,json_dir)

def ocr_space_url(url, overlay=False, api_key='helloworld', language='ce'):
		""" OCR.space API request with remote file.
				Python3.5 - not tested on 2.7
		:param url: Image url.
		:param overlay: Is OCR.space overlay required in your response.
										Defaults to False.
		:param api_key: OCR.space API key.
										Defaults to 'helloworld'.
		:param language: Language code to be used in OCR.
										List of available language codes can be found on https://ocr.space/OCRAPI
										Defaults to 'en'.
		:return: Result in JSON format.
		"""

		payload = {
			'url': url,
			'isOverlayRequired': overlay,
			'apikey': api_key,
			'language': language,
		}
		logger.debug("Cekam na odpoved...")
		r = requests.post(
			'https://api.ocr.space/parse/image',
			data=payload
		)
		#print("ocr_space_url",type(r.content.decode()))
		return r.content.decode()

def ziskej_jmeno(text):
	shoda = re.match('.*(([Zzr]as[tr](?!aven[oiá]|upitelstvo|avil?|upov[áa][nt]|avuje|upci)[^,:]+)[,:.]?\s+(advok|se)).*', text, flags=re.DOTALL)
	jmeno = None
	if shoda is not None:
		advokat = shoda.group(2)
		if len(advokat) > 15:
			seznam = []
			delka = 0
			for s in advokat.split(' '):
				zaznam = s.strip()
				if zaznam != '' and len(zaznam) > 1 and "advok" not in zaznam:
					seznam.append(zaznam)
					delka += len(zaznam)
			if len(seznam) >=2:
				if "ovou" in seznam[-2].strip():
					jmeno = seznam[-3].strip()+" "+seznam[-2].strip()+"-"+seznam[-1].strip()
				else:
					jmeno = seznam[-2].strip()+" "+seznam[-1].strip()
	return jmeno

def verify(spis_znacka,zneni_odkaz,key="helloworld"):
	filename = spis_znacka.replace('/','-')+"-text.txt"		
	if os.path.exists(txt_dir_path+"/"+filename): #neexistuje soubor s textem
		logger.info("Existuje soubor s textem (skip) - %s",txt_dir_path+"/"+filename)
		return True
	else:
		result = None
		text = None
		advokat = None
		logger.info("OCR prevod: %s",zneni_odkaz)
		test_url = ocr_space_url(url=zneni_odkaz,api_key=key)
		result = json.loads(test_url)
		#print("verify",type(result))
		if result is not None and type(result) is not str:
			if result['ParsedResults'] is not None:
				text = result['ParsedResults'][0]['ParsedText']
				#logger.debug("Text z OCR:\n'%s'",text)
				if text is not None and len(text) > 1:
					with codecs.open(txt_dir_path+"/"+filename,'w',encoding="utf-8") as text_file:
						text_file.write(text)
					advokat = ziskej_jmeno(text)
					logger.info("Advokát(ka): %s --> %s",advokat)
					return True
				else:
					logger.warning("\n"+pprint.pformat(result))
					logger.warning("Žádný text nebo se nepodařil převod")
					return True
			else:
				logger.warning("\n"+pprint.pformat(result))
				logger.error("result['ParsedResults'] is None")
				return None
		elif type(result) is str:
			logger.warning(result)
			logger.warning("Vyčerpán počet volání - budu čekat")
			return False
		else:
			logger.warning(pprint.pformat(result))
			logger.error("Chyba - žádná odpověď")
			return True

def main():
	if not os.path.exists("output_data/seznam.json"):
		logger.error("Neexistuje zdrojový soubor 'seznam.json'")
		sys.exit()
	with codecs.open('output_data/seznam.json','r',encoding = 'utf-8') as raw:  
		seznam = json.loads(raw.read())
	i = 0
	celkem = 0
	#while len(seznam) > 10:
	for znacka, odkaz in seznam.items():
		b_result = verify(znacka,odkaz)
		if b_result is True:
			i+=1
			#seznam.pop(znacka)
		elif b_result is False:
			#print(i)
			logger.info("Vyčerpán počet volání (i = %s or %s) - zkusím to znovu...",i,b_result)
			if verify(znacka,odkaz,key="dfcc73f08588957"): # stejny vstup
				i+=1
			else:
				logger.info("Vyčerpán počet volání (i = %s or %s) - čekám 10 minut...",i,b_result)
				time.sleep(630)
				celkem += i
				i = 0
			logger.info("Zpracováno %s z %s",str(celkem),str(len(seznam)))
			
				#seznam.pop(znacka)
		else:
			if verify(znacka,odkaz): # stejny vstup
				i+=1
				#seznam.pop(znacka)

if __name__ == '__main__':
	if not os.path.exists(out_dir):
		os.mkdir(out_dir)
		print("Vytvořena složka '"+out_dir+"'")
	if not os.path.exists(txt_dir_path):
		os.mkdir(txt_dir_path)
		print("Vytvořena složka '"+txt_dir_path+"'")
	else:
		print("Existuje TXT")
	if not os.path.exists(json_dir_path):
		os.mkdir(json_dir_path)
		print("Vytvořena složka '"+json_dir_path+"'")
	else:
		print("Existuje JSON")
	main()

