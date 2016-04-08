#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# coding=utf-8

from ghost import Ghost
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import math
import io
import os
import re
import sys
import codecs
import collections
import time
import csv
import json
import requests

import logging

base_url = "http://nssoud.cz/"
url = "http://nssoud.cz/main0Col.aspx?cls=JudikaturaSimpleSearch&pageSource=0"
path ="C:\\Users\\Public\\Pictures\\screens"
out_dir = "output_data"
json_dir = "JSON"
txt_dir = "TXT"
txt_dir_path = os.path.join(out_dir,txt_dir)
json_dir_path = os.path.join(out_dir,json_dir)
b_screens = False # porizovat screenshoty cinnosti
# precompile regex
p_celkem = re.compile(r'(\d+)$')
p_forma = re.compile(r'[a-z<>]{4}\s+(.+)\s+')

# nastaveni logovani
logger = logging.getLogger("%(file)s")
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler("advokat_log.txt",mode="w",encoding='utf-8')
fh.setLevel(logging.DEBUG)
# create console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(funcName)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
# add the handlers to logger
logger.addHandler(ch)
logger.addHandler(fh)

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
		return r.content.decode()

def kolik(celkem_str,zaznamu):
	m = p_celkem.search(celkem_str)
	celkem = m.group(1)
	stran = math.ceil(int(celkem)/int(zaznamu))
	logger.info("celkem: %s => stran: %s",celkem,stran)
	return (celkem,stran)

def page_has_loaded():
	page_state, resources = session.evaluate(
		'document.readyState;'
	)
	
	if resources:
		#print(page_state,resources)
		return page_state == 'complete'
	else:
		return False

def na_zacatek():
	session.click("#_ctl0_ContentPlaceMasterPage__ctl0_pnPaging1_Repeater2__ctl0_Linkbutton2")
	session.wait_for(page_has_loaded,"Čas vypršel - Na zacatek",timeout = 1000)

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

def ziskej_data(rows,znacka):
	strana = []
	#odkazy = []
	for item in rows[1:]:
		children = item.findAll("td")
		spis_znacka = children[1].getText().replace("\n",'').strip() # ziskani oznaceni pripadu
		# odkaz na dokument s rozhodnutim
		zneni = children[1].select_one('a[href*=SOUDNI_VYKON]')
		zneni_odkaz = None
		filename = spis_znacka.replace('/','-')+"-"
		if zneni is not None:
			if not os.path.exists(txt_dir_path+"/"+filename+"text.txt"): #neexistuje soubor s textem
				zneni_odkaz = children[1].select_one('a[href*=SOUDNI_VYKON]')['href']
				zneni_odkaz = urljoin(base_url,zneni_odkaz)
				odkazy[spis_znacka] = zneni_odkaz
			else:
				logger.info("Existuje soubor s textem (skip) - %s",txt_dir_path+"/"+filename+"txt.txt")

		str_forma = str(children[2]).replace("\n",'').strip()
		#logger.debug("Str_forma: %s",str_forma)
		m = p_forma.search(str_forma)
		line= m.group(1)
		#logger.debug("Line: %s",line)
		forma = [x.strip() for x in line.split("<br>")]
		soud = children[3].getText().replace("\n",'').strip()

		str_datum = children[4].getText().replace("\n",'').strip()
		datum = [x.strip() for x in str_datum.split("/ ")]

		result = None
		text = None
		advokat = None
		if zneni_odkaz is not None:
			if not os.path.exists(txt_dir_path+"/"+filename+"text.txt"):
				logger.info("OCR prevod: %s",zneni_odkaz)
				#test_url = ocr_space_url(url=zneni_odkaz)
				#result = json.loads(test_url)
			
				if result is not None and type(result) is not str:
					logger.warning(result)
					if result['ParsedResults'] is not None:
						text = result['ParsedResults'][0]['ParsedText']
						logger.debug("Text z OCR:\n'%s'",text)
						if text is not None or len(text) > 1:
							with codecs.open(text_dir_path+"/"+filename+"text.txt",'w',encoding='utf-8') as text_file:
								text_file.write(text)

						advokat = ziskej_jmeno(text)
		polozka = {"typ" : znacka, "znacka" : spis_znacka, "forma" : forma, "soud" : soud, "datum" : datum, "odkaz" : zneni_odkaz, "advokat" : advokat}
		strana.append((spis_znacka,polozka))

		# vytvoreni JSON zaznamu
		"""
		with codecs.open(json_dir_path+"/"+filename+".json",'w',encoding='utf-8') as file_json:
			json.dump(polozka,file_json,sort_keys = True, indent = 4, ensure_ascii = False)
		"""
		writer.writerow(polozka) # zapis zaznamu do CSV

	return strana

def zobraz_data(znacka,hodnota):
	# prvni zaznamy
	if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_ddlRejstrik"):
		logger.debug("Change spisová značka - %s",znacka)
		session.set_field_value("#_ctl0_ContentPlaceMasterPage__ctl0_ddlRejstrik",hodnota)
		#time.sleep(1)
	if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_btnFind"):
		logger.debug("Klik - Hledat")
		session.click("#_ctl0_ContentPlaceMasterPage__ctl0_btnFind")
		#result, resources = session.wait_for_selector("#_ctl0_ContentPlaceMasterPage__ctl0_grwA")
		#time.sleep(10)
		session.wait_for(page_has_loaded,"Čas vypršel - Hledat",timeout=5000)
		
		if b_screens:
			logger.debug("\t_find_screen_"+znacka+".png")
			session.capture_to(path+"/_find_screen_"+znacka+".png")
	# vice zaznamu na strance

	if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_ddlRowCount"):
		value, resources = session.evaluate("document.getElementById('_ctl0_ContentPlaceMasterPage__ctl0_ddlRowCount').value")
		#print("value != '30'",value != "30")
		if value != "30":
			logger.debug("Change row count")
			session.set_field_value("#_ctl0_ContentPlaceMasterPage__ctl0_ddlRowCount",'30')
			#time.sleep(1)
			#button = br.find_element_by_name("_ctl0:ContentPlaceMasterPage:_ctl0:btnChangeCount")
			if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_btnChangeCount"):
				logger.debug("Klik - Change")
				result, resources = session.click("#_ctl0_ContentPlaceMasterPage__ctl0_btnChangeCount")
				#result, resources = session.wait_for_selector("#_ctl0_ContentPlaceMasterPage__ctl0_grwA")
				#time.sleep(10)
				session.wait_for(page_has_loaded,"Čas vypršel - Změnit",timeout=5000)

				if b_screens:
					logger.debug("\tfind_screen_"+znacka+"_change_row_count.png")
					session.capture_to(path+"/_find_screen_"+znacka+"_change_row_count.png")

def listuj(stran,zaznamu,celkem,znacka):
	all_data = []
	logger.debug("Stran: %d",stran)
	#odkazy = []
	for i in range(1,stran+1): # pruchod stranami
		response = session.content
		soup = BeautifulSoup(response,"html.parser")
		#print (soup)
		table = soup.find("table",id="_ctl0_ContentPlaceMasterPage__ctl0_grwA")
		if table == None:
			logger.error("Tady není tabulka")
		else:
			rows = table.findAll("tr")
			#print(len(rows),i,stran)
			if i >= 12:
				logger.debug("(%d) - %d < 10 --> %s",(stran ),(i),(stran) - i < 10)
				# posledni strany
				if (stran) - (i+1) < 10:
					pozice = [0,1,2,3,4,5,6,7,8,9,10]
					logger.debug("%d",pozice[(i-(stran))])
					cislo = str(pozice[(i-(stran))]+12)
				else:
					cislo = "12"
			else:
				cislo = str(i+1)

			logger.debug("cislo = %s",cislo)
	
			if b_screens:
				session.capture_to(path+"/find_screen_"+znacka+"_0"+str(i)+".png",None,selector="#pagingBox0")

			strana = ziskej_data(rows,znacka)
			#odkazy.extend(strana_odkazy)

			zaznamu += len(strana)
			logger.info("(%d) Zpracováno %s záznamů z %s",i,zaznamu,celkem) # info o prubehu
			if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_pnPaging1_Repeater2__ctl"+cislo+"_LinkButton1") and i+1 < (stran + 1):
				link_id = "_ctl0_ContentPlaceMasterPage__ctl0_pnPaging1_Repeater2__ctl"+cislo+"_LinkButton1"
				logger.debug("\tKlik - strana %d (%s)",(i+1),link_id)
				try:
					result, resources = session.click("#"+link_id)
					session.wait_for(page_has_loaded,"Čas vypršel - Listuj",timeout = 1000)	
				except Exception:
					logger.error("Chyba (listuj) - Zavírám browser", exc_info=True)
					logger.debug("error_"+znacka+"("+str(i+1)+").png")
					session.capture_to(path+"/error_"+znacka+"("+str(i+1)+").png")
					return False
	#print(odkazy,"\n",len(odkazy))
	#return odkazy
	return True

def zpracuj_nssoud():
	znacky = {"As" : '12', "Ads" : '10', "Afs": '11', "Ars": '116', "Azs": '9'}
	fieldnames= ['typ','znacka','forma','soud','datum','odkaz','advokat']
	row_count = 30

	global seznamfile
	global writer
	global odkazy

	odkazy = {}

	csvfile = open(out_dir+"/data.csv",'w',newline='')

	writer = csv.DictWriter(csvfile,fieldnames=fieldnames,delimiter=";")
	writer.writeheader()
	#seznam_odkazu = []
	for znacka in znacky.keys():
		logger.info("-----------------------------------------------------")
		logger.info(znacka)
		zobraz_data(znacka,znacky[znacka])
		global zaznamu
		zaznamu, resources = session.evaluate("document.getElementById('_ctl0_ContentPlaceMasterPage__ctl0_ddlRowCount').value")
		#zaznamu = "30" #hack pro testovani
		if zaznamu is not None and int(zaznamu) != row_count:
			logger.warning(int(zaznamu) != row_count)
			logger.error("Nepovedlo se zobrazit data")
			if b_screens:
				logger.debug("error_"+znacka+".png")
				session.capture_to(path+"/error_"+znacka+".png")
			return False

		info,resources = session.evaluate("document.getElementById('_ctl0_ContentPlaceMasterPage__ctl0_pnPaging1_Repeater3__ctl0_Label2').innerHTML")
		celkem = 0
		stran = 0
		if info:
			#zaznamu = "20" #hack pro testovani
			celkem_str = info.replace("<b>","").replace("</b>","")
			celkem,stran = kolik(celkem_str,zaznamu)
		else:
			return False
		cislo = 1
		zaznamu = 0
		#testovani
		stran = 1

		result = listuj(stran,zaznamu,celkem,znacka)
		if result is False:
			logger.warning("Result of 'listuj' is False")
			csvfile.close()
			return False
		#else:
			#seznam_odkazu.extend(result)
			#print(seznam_odkazu,"\n",len(seznam_odkazu))
		na_zacatek()
	csvfile.close()
	# zapis odkazu do JSON pro dalsi zpracovani
	with codecs.open(out_dir+"/seznam2.json",'w',encoding='utf-8') as seznam_file:
		#seznam_file.write("{")
		#for record in seznam_odkazu:
			#znacka, odkaz = record.items()
		output = json.dump(odkazy,seznam_file,sort_keys = True, indent = 4, ensure_ascii = False)
		#seznam_file.write("}")
	return True
	#return collections.OrderedDict(all_r)

def main():
	global ghost
	ghost = Ghost()
	global session
	session = ghost.start(download_images=False,show_scrollbars=False)
	logger.info("Otevírám browser")
	session.open(url)

	if b_screens:
		logger.debug("_screen.png")
		session.capture_to(path+"/_screen.png")

	result = zpracuj_nssoud()
	#print(result)
	if result is True:
		logger.info("Zavírám browser")
	else:
		logger.error("Chyba (main)- Zavírám browser")
	session.exit()
	ghost.exit()

if __name__ == "__main__":
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
	if b_screens:
		if not os.path.exists(path):
			os.mkdir(path)
			print("Vytvořena složka '"+path+"'")
		logger.debug("Mažu staré screeny")
		os.system("erase /Q "+path)
	main()

