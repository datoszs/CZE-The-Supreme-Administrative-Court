#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# coding=utf-8

from ghost import Ghost
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from optparse import OptionParser
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
url = "http://nssoud.cz/main0Col.aspx?cls=JudikaturaBasicSearch&pageSource=0"
path ="screens"
documents_dir = "PDF"
txt_dir = "TXT"

out_dir = ""
ooutput_file = ""
date_from = ""
date_to = ""
days = 0

b_screens = False # capture screenshots?
# precompile regex
p_re_records = re.compile(r'(\d+)$')
p_re_decisions = re.compile(r'[a-z<>]{4}\s+(.+)\s+')

# settings of logging
logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(__file__+"_log.txt",mode="w",encoding='utf-8')
fh.setLevel(logging.DEBUG)
# create console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(funcName)-15s - %(levelname)-8s: %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
# add the handlers to logger
logger.addHandler(ch)
logger.addHandler(fh)

def parameters():
	usage = "usage: %prog [options]"
	parser = OptionParser(usage)
	parser.add_option("-l","--last-days",action="store",type="int", dest="interval",default=None,help="number of days to checking")
	parser.add_option("-d","--output-directory",action="store",type="string", dest="dir",default="output_data",help="Path to output directory")
	parser.add_option("-f","--date-from",action="store",type="string", dest="date_from",default=None,help="Start date of range ")
	parser.add_option("-t","--date-to",action="store",type="string", dest="date_to",default=None,help="End date of range")
	parser.add_option("-c","--capture",action="store_true",dest="screens",default=False,help="Capture screenshots?")
	parser.add_option("-o","--output-file",action="store",type="string",dest="filename",default="data",help="Name of output CSV file")
	(options, args) = parser.parse_args()
	options = vars(options)

	print(args,options,type(options))
	return options

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
		logger.debug("Waiting for response...")
		r = requests.post(
			'https://api.ocr.space/parse/image',
			data=payload
		)
		return r.content.decode() # off topic

def how_many(str_info,displayed_records):
	"""
	find number of records and compute count of pages
	@param str_info - info element as string
	@param displayed_records - number of displayed records
	"""
	m = p_re_records.search(str_info)
	number_of_records = m.group(1)
	count_of_pages = math.ceil(int(number_of_records)/int(displayed_records))
	logger.info("records: %s => pages: %s",number_of_records,count_of_pages)
	return (number_of_records,count_of_pages)

def page_has_loaded():
	"""
	checking state of page
	"""
	page_state, resources = session.evaluate(
		'document.readyState;'
	)
	
	if resources:
		#print(page_state,resources)
		return page_state == 'complete'
	else:
		return False

def first_page():
	"""
	go to first page on find query
	"""

	session.click("#_ctl0_ContentPlaceMasterPage__ctl0_pnPaging1_Repeater2__ctl0_Linkbutton2")
	session.wait_for(page_has_loaded,"Timeout - go to first page",timeout = 1000)

def check_decisions(decisions):
	# //TODO
	if "Rozsudek" in decisions[0]:
		if decisions[1] in []:
			return True
	elif "Usnesení" in decisions[0]:
		if decisions[1] in []:
			return True
	return False

def extract_data(rows):
	"""
	extract relevant data from page
	@param rows - list of row elements
	"""
	for record in rows[1:]:
		columns = record.findAll("td") # columns of table in the row
		link_elem = columns[1].select_one('a[href*=SOUDNI_VYKON]')
		link = None
		# link to the decision's document
		if link_elem is not None:
			link = link_elem['href']
			link = urljoin(base_url,link)
		else:
			continue # case without document

		# extract decision results
		decisions_str = str(columns[2]).replace("\n",'').strip()
		m = p_re_decisions.search(decisions_str)
		line= m.group(1)
		decision_result = [x.replace('\"','\'').strip() for x in line.split("<br>")]
		# TODO: check decisions
		decisions = {'1':decision_result[0],'2':decision_result[1]}
		decision_result = json.dumps(decisions,sort_keys = True,ensure_ascii = False)
		case_number= columns[1].getText().replace("\n",'').strip()
		mark = case_number.split("-")[0].strip() # registry mark isn't case number
		
		court = columns[3].getText().replace("\n",'').strip()
		
		str_date = columns[4].getText().replace("\n",'').strip()
		date = [x.strip() for x in str_date.split("/ ")]
		if len(date) >= 1:
			date = date[0]
			# convert date from format dd.mm.YYYY to YYYY-mm-dd
			date = datetime.strptime(date, '%d.%m.%Y').strftime('%Y-%m-%d')

		filename = case_number.replace('/','-')+"-"
		item = {
			"registry_mark" : mark,
			"decision_date" : date,
			"court_name" : court,
			"web_path" : link,
			"local_path" : os.path.join(txt_dir_path,filename+"text.txt"),
			"decision_result" : decision_result,
			"case_number" : case_number
		}
		# //TODO: increment counter of all records
		writer_records.writerow(item) # write item to CSV
		writer_links.writerow({"case_number":case_number, "link":link})# write list of links for next processing

def view_data(mark_type,value,days=None,date_from=None,date_to=None):
	"""
	sets forms parameters for viewing data
	@param mark_type - text identificator of mark type
	@param value - number identificator for formular
	@param days - how many last days
	@param date_from - start date of range
	@param date_to - end date of range

	"""
	if date_from is not None and date_to is not None:
		# setting range search
		logger.info("Records from the period %s -> %s",date_from,date_to)
		# id = _ctl0_ContentPlaceMasterPage__ctl0_txtDatumOd
		if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_txtDatumOd"):
			session.set_field_value("#_ctl0_ContentPlaceMasterPage__ctl0_txtDatumOd",date_from)
		# id = _ctl0_ContentPlaceMasterPage__ctl0_txtDatumDo
		if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_txtDatumDo"):
			session.set_field_value("#_ctl0_ContentPlaceMasterPage__ctl0_txtDatumDo",date_to)
	elif days is not None:
		logger.info("Only new records for %s days",days)
		# search settings on the last records
		# id (checkbox) = _ctl0_ContentPlaceMasterPage__ctl0_chkPrirustky
		if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_chkPrirustky"):
			logger.debug("Change checkbox of last days")
			session.set_field_value("#_ctl0_ContentPlaceMasterPage__ctl0_chkPrirustky",True)
		# id (select) = _ctl0_ContentPlaceMasterPage__ctl0_ddlPosledniDny
		if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_ddlPosledniDny"):
			logger.debug("Change value of last days")
			session.set_field_value("#_ctl0_ContentPlaceMasterPage__ctl0_ddlPosledniDny",str(days))

	# shows several first records
	if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_ddlRejstrik"): # change mark type in select
		logger.debug("Change mark type - %s",mark_type)
		session.set_field_value("#_ctl0_ContentPlaceMasterPage__ctl0_ddlRejstrik",value)
		#time.sleep(1)
	if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_btnFind"): # click on find button
		logger.debug("Click - find")
		session.click("#_ctl0_ContentPlaceMasterPage__ctl0_btnFind")
		#result, resources = session.wait_for_selector("#_ctl0_ContentPlaceMasterPage__ctl0_grwA")
		#time.sleep(10)
		session.wait_for(page_has_loaded,"Timeout - find",timeout=5000)
		
		if b_screens:
			logger.debug("\t_find_screen_"+mark_type+".png")
			session.capture_to(path+"/_find_screen_"+mark_type+".png")
	# change value of row count on page
	if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_ddlRowCount"): 
		value, resources = session.evaluate("document.getElementById('_ctl0_ContentPlaceMasterPage__ctl0_ddlRowCount').value")
		#print("value != '30'",value != "30")
		if value != "30":
			logger.debug("Change row count")
			session.set_field_value("#_ctl0_ContentPlaceMasterPage__ctl0_ddlRowCount",'30')
			#time.sleep(1)
			#button = br.find_element_by_name("_ctl0:ContentPlaceMasterPage:_ctl0:btnChangeCount")
			if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_btnChangeCount"):
				logger.debug("Click - Change")
				result, resources = session.click("#_ctl0_ContentPlaceMasterPage__ctl0_btnChangeCount")
				#result, resources = session.wait_for_selector("#_ctl0_ContentPlaceMasterPage__ctl0_grwA")
				#time.sleep(10)
				session.wait_for(page_has_loaded,"Timeout - Change",timeout=5000)

				if b_screens:
					logger.debug("\tfind_screen_"+mark_type+"_change_row_count.png")
					session.capture_to(path+"/_find_screen_"+mark_type+"_change_row_count.png")

def walk_pages(count_of_pages):
	"""
	make a walk through pages of results
	@param count_of_pages - over how many pages we have to go
	"""
	logger.debug("count_of_pages: %d",count_of_pages)
	for i in range(1,count_of_pages+1): # walk pages
		response = session.content
		soup = BeautifulSoup(response,"html.parser")
		table = soup.find("table",id="_ctl0_ContentPlaceMasterPage__ctl0_grwA")

		if table is None: # has page table with records?
			logger.error("There is not table")
		else:
			rows = table.findAll("tr") # record on the page

			if i >= 12:
				logger.debug("(%d) - %d < 10 --> %s",(count_of_pages ),(i),(count_of_pages) - i < 10)
				# special compute for last pages
				if (count_of_pages) - (i+1) < 10:
					positions = [0,1,2,3,4,5,6,7,8,9,10]
					logger.debug("%d",positions[(i-(count_of_pages))])
					page_number = str(positions[(i-(count_of_pages))]+12)
				else:
					page_number = "12" # next page element has constant ID
			else:
				page_number = str(i+1) # few first pages

			logger.debug("Number = %s",page_number)
	
			if b_screens:
				session.capture_to(path+"/find_screen_0"+str(i)+".png",None,selector="#pagingBox0")

			extract_data(rows)

			#logger.info("(%d) Zpracováno %s záznamů z %s",i,number_of_records,celkem) # info o prubehu
			if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_pnPaging1_Repeater2__ctl"+page_number+"_LinkButton1") and i+1 < (count_of_pages + 1):
				link_id = "_ctl0_ContentPlaceMasterPage__ctl0_pnPaging1_Repeater2__ctl"+page_number+"_LinkButton1"
				logger.debug("\tClick - Page %d (%s)",(i+1),link_id)
				try:
					result, resources = session.click("#"+link_id)
					session.wait_for(page_has_loaded,"Timeout - walk_pages",timeout = 1000)	
				except Exception:
					logger.error("Error (walk_pages) - close browser", exc_info=True)
					logger.debug("error_("+str(i+1)+").png")
					session.capture_to(path+"/error_("+str(i+1)+").png")
					return False
	return True

def process_court():
	"""
	creates files for processing and saving data, start point for processing
	"""
	case_types = {"As" : '12', "Ads" : '10', "Afs": '11', "Ars": '116', "Azs": '9'}
	fieldnames= ['court_name','registry_mark','decision_date','web_path','local_path', 'decision_result','case_number']
	row_count = 30

	global writer_links
	global writer_records
	global list_of_links

	list_of_links = {}

	csv_records = open(os.path.join(out_dir,output_file),'w',newline='')
	csv_links = open(out_dir+"/list_of_links.csv",'w',newline='')

	writer_records = csv.DictWriter(csv_records,fieldnames=fieldnames,delimiter=";")
	writer_links = csv.DictWriter(csv_links,fieldnames=["case_number","link"],delimiter=";")
	writer_links.writeheader()
	writer_records.writeheader()

	for case_type in case_types.keys():
		logger.info("-----------------------------------------------------")
		logger.info(case_type)
		view_data(case_type,case_types[case_type],days=days,date_from=date_from,date_to=date_to)
		# view_data(case_type,case_types[case_type],date_from="1.1.2016",date_to="24.4.2016")
		# view_data(case_type,case_types[case_type],days=7)
		# view_data(case_type,case_types[case_type])
		number_of_records, resources = session.evaluate("document.getElementById('_ctl0_ContentPlaceMasterPage__ctl0_ddlRowCount').value")
		#number_of_records = "30" #hack pro testovani
		if number_of_records is not None and int(number_of_records) != row_count:
			logger.warning(int(number_of_records) != row_count)
			logger.error("Failed to display data")
			if b_screens:
				logger.debug("error_"+case_type+".png")
				session.capture_to(path+"/error_"+case_type+".png")
			return False
		#my_result = session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_pnPaging1_Repeater3__ctl0_Label2")
		#print (my_result)
		if not session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_pnPaging1_Repeater3__ctl0_Label2"):
			logger.info("No records")
			continue
		info_elem, resources = session.evaluate("document.getElementById('_ctl0_ContentPlaceMasterPage__ctl0_pnPaging1_Repeater3__ctl0_Label2').innerHTML")
		


		if info_elem:
			#number_of_records = "20" #hack pro testovani
			str_info = info_elem.replace("<b>","").replace("</b>","")
			number_of_records, count_of_pages = how_many(str_info,number_of_records)
		else:
			return False

		#testovani
		#if count_of_pages >=5:
		#	count_of_pages = 2

		result = walk_pages(count_of_pages)
		if result == False:
			logger.warning("Result of 'walk_pages' is False")
			csv_records.close()
			csv_links.close()
			return False
		first_page()
	csv_records.close()
	csv_links.close()
	return True

def main():
	global ghost
	ghost = Ghost()
	global session
	session = ghost.start(download_images=False,show_scrollbars=False)
	logger.info("Opening browser")
	session.open(url)

	if b_screens:
		logger.debug("_screen.png")
		session.capture_to(path+"/_screen.png")

	result = process_court()
	#print(result)
	if result == True:
		logger.info("Closing browser")
	else:
		logger.error("Error (main)- closing browser")
	session.exit()
	ghost.exit()

if __name__ == "__main__":
	options = parameters()
	out_dir = options["dir"]
	days = options["interval"]
	date_from = options["date_from"]
	date_to = options["date_to"]
	b_screens = options["screens"]
	output_file = options["filename"]
	if ".csv" not in output_file:
		output_file += ".csv"
	txt_dir_path = os.path.join(out_dir,txt_dir)
	documents_dir_path = os.path.join(out_dir,documents_dir)

	if not os.path.exists(out_dir):
		os.mkdir(out_dir)
		print("Folder was created '"+out_dir+"'")
	if not os.path.exists(txt_dir_path):
		os.mkdir(txt_dir_path)
		print("Folder was created '"+txt_dir_path+"'")
	else:
		print("Folder"+"'"+txt_dir_path+"' "+"now exists")
	if not os.path.exists(documents_dir_path):
		os.mkdir(documents_dir_path)
		print("Folder was created '"+documents_dir_path+"'")
	else:
		print("Folder"+"'"+documents_dir_path+"' "+"now exists")
	if b_screens:
		if not os.path.exists(path):
			os.mkdir(path)
			print("Folder was created '"+path+"'")
		logger.debug("Erasing old scree")
		os.system("erase /Q "+path)
	main()