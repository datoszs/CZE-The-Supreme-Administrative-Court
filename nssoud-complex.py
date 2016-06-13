#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# coding=utf-8

from ghost import Ghost
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from optparse import OptionParser
from collections import OrderedDict
from tqdm import tqdm
import math
import io
import os
import re
import sys
import codecs
import time
import csv
import json
import logging

base_url = "http://nssoud.cz/"
url = "http://nssoud.cz/main0Col.aspx?cls=JudikaturaBasicSearch&pageSource=0"
hash_id = datetime.now().strftime("%d-%m-%Y")
screens_dir ="screens_"+hash_id
documents_dir = "PDF"
txt_dir = "TXT"
html_dir = "HTML"

main_timeout = 10000
saved_pages = 0

b_screens = False # capture screenshots?
# precompile regex
p_re_records = re.compile(r'(\d+)$')
p_re_decisions = re.compile(r'[a-z<>]{4}\s+(.+)\s+')

def set_logging():
	# settings of logging
	global logger
	logger = logging.getLogger(__file__)
	logger.setLevel(logging.DEBUG)
	fh_d = logging.FileHandler(os.path.join(out_dir,__file__[0:-3]+"_"+hash_id+"_log_debug.txt"),mode="w",encoding='utf-8')
	fh_d.setLevel(logging.DEBUG)
	fh_i = logging.FileHandler(os.path.join(out_dir,__file__[0:-3]+"_"+hash_id+"_log.txt"),mode="w",encoding='utf-8')
	fh_i.setLevel(logging.INFO)
	# create console handler
	ch = logging.StreamHandler()
	ch.setLevel(logging.INFO)
	# create formatter and add it to the handlers
	formatter = logging.Formatter(u'%(asctime)s - %(funcName)-15s - %(levelname)-8s: %(message)s')
	ch.setFormatter(formatter)
	fh_d.setFormatter(formatter)
	fh_i.setFormatter(formatter)
	# add the handlers to logger
	logger.addHandler(ch)
	logger.addHandler(fh_d)
	logger.addHandler(fh_i)

def parameters():
	usage = "usage: %prog [options]"
	parser = OptionParser(usage)
	parser.add_option("-l","--last-days",action="store",type="int", dest="interval",default=None,help="number of days to checking")
	parser.add_option("-d","--output-directory",action="store",type="string", dest="dir",default="output_data",help="Path to output directory")
	parser.add_option("-f","--date-from",action="store",type="string", dest="date_from",default=None,help="Start date of range (d. m. yyyy)")
	parser.add_option("-t","--date-to",action="store",type="string", dest="date_to",default=None,help="End date of range (d. m. yyyy)")
	parser.add_option("-c","--capture",action="store_true",dest="screens",default=False,help="Capture screenshots?")
	parser.add_option("-o","--output-file",action="store",type="string",dest="filename",default="nss_csv",help="Name of output CSV file")
	parser.add_option("-e","--extraction",action="store_true",dest="extraction",default=False,help="Make only extraction without download new data")
	(options, args) = parser.parse_args()
	options = vars(options)

	print(args,options,type(options))
	return options

def make_soup(path):
	soup = BeautifulSoup(codecs.open(path,encoding="utf-8"),"html.parser")
	return soup

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
	session.wait_for(page_has_loaded,"Timeout - go to first page",timeout = main_timeout)

def extract_data(response,html_file):
	"""
		save current page as HTML file for later extraction
	"""
	logger.debug("Save file '%s'" % html_file)
	with codecs.open(os.path.join(html_dir_path,html_file),"w",encoding="utf-8") as f:
		f.write(response)

def make_record(soup):
	"""
	extract relevant data from page
	"""
	table = soup.find("table",id="_ctl0_ContentPlaceMasterPage__ctl0_grwA")
	rows = table.findAll("tr")
	logger.debug("Records on pages: %d" % len(rows[1:]))

	for record in rows[1:]:
		columns = record.findAll("td") # columns of table in the row

		case_number= columns[1].getText().replace("\n",'').strip()
		# extract decision results
		decisions_str = str(columns[2]).replace("\n",'').strip()
		m = p_re_decisions.search(decisions_str)
		line= m.group(1)
		decision_result = [x.replace('\"','\'').strip() for x in line.split("<br>")]
		if len(decision_result) > 1:
			decisions = {'1':decision_result[0],'2':decision_result[1]}
		else:
			decisions = {'1':decision_result[0]}
		decision_result = json.dumps(decisions,sort_keys = True,ensure_ascii = False)

		link_elem = columns[1].select_one('a[href*=SOUDNI_VYKON]')
		link = None
		# link to the decision's document
		if link_elem is not None:
			link = link_elem['href']
			link = urljoin(base_url,link)
		else:
			writer_links.writerow({"case_number":case_number, "link":link, "decision_result" : decision_result})# write list of links for next processing
			continue # case without document

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
		
		writer_records.writerow(item) # write item to CSV
		logger.debug(case_number)
		writer_links.writerow({"case_number":case_number, "link":link, "decision_result" : decision_result})# write list of links for next processing

def extract_information(extract=None):
	"""
		extract informations from HTML files and write to CSVs
	"""
	html_files = [os.path.join(html_dir_path,fn) for fn in next(os.walk(html_dir_path))[2]]
	if extract is True:
		saved_pages = len(html_files)
	if len(html_files) == saved_pages:
		global writer_links
		global writer_records

		fieldnames= ['court_name','registry_mark','decision_date','web_path','local_path', 'decision_result','case_number']
		csv_records = open(os.path.join(out_dir,output_file),'w',newline='',encoding="utf-8")
		csv_links = open(os.path.join(out_dir,"links_"+output_file),'w',newline='',encoding="utf-8")

		writer_records = csv.DictWriter(csv_records,fieldnames=fieldnames,delimiter=";")
		writer_links = csv.DictWriter(csv_links,fieldnames=["case_number","link","decision_result"],delimiter=";")
		writer_links.writeheader()
		writer_records.writeheader()

		t = tqdm(html_files)
		for html_f in t:
			logger.debug(html_f)
			make_record(make_soup(html_f))
			t.update()
			#print(i)
			"""i += 1
			if i==80:
				break"""

		csv_records.close()
		csv_links.close()

def view_data(mark_type,value,days=None,date_from=None,date_to=None):
	"""
	sets forms parameters for viewing data
	@param mark_type - text identificator of mark type
	@param value - number identificator for formular
	@param days - how many last days
	@param date_from - start date of range
	@param date_to - end date of range

	"""
	if date_from is not None :
		# setting range search
		logger.info("Records from the period %s -> %s",date_from,date_to)
		# id = _ctl0_ContentPlaceMasterPage__ctl0_txtDatumOd
		if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_txtDatumOd"):
			session.set_field_value("#_ctl0_ContentPlaceMasterPage__ctl0_txtDatumOd",date_from)
	if date_to is not None:
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
	if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_ddlSortName"):
		session.set_field_value("#_ctl0_ContentPlaceMasterPage__ctl0_ddlSortName","2")
		session.set_field_value("#_ctl0_ContentPlaceMasterPage__ctl0_ddlSortDirection","0")

	if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_btnFind"): # click on find button
		logger.debug("Click - find")
		session.click("#_ctl0_ContentPlaceMasterPage__ctl0_btnFind",expect_loading = True)
		#result, resources = session.wait_for_selector("#_ctl0_ContentPlaceMasterPage__ctl0_grwA")
		#time.sleep(10)
		#session.wait_for(page_has_loaded,"Timeout - find",timeout=main_timeout)
		
		if b_screens:
			logger.debug("\t_find_screen_"+mark_type+".png")
			session.capture_to(screens_dir_path+"/_find_screen_"+mark_type+".png")
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
				result, resources = session.click("#_ctl0_ContentPlaceMasterPage__ctl0_btnChangeCount",expect_loading = True)
				#result, resources = session.wait_for_selector("#_ctl0_ContentPlaceMasterPage__ctl0_grwA")
				#time.sleep(10)
				#session.wait_for(page_has_loaded,"Timeout - Change",timeout=main_timeout)

				if b_screens:
					logger.debug("\tfind_screen_"+mark_type+"_change_row_count.png")
					session.capture_to(screens_dir+"/_find_screen_"+mark_type+"_change_row_count.png")

def walk_pages(count_of_pages,case_type):
	"""
	make a walk through pages of results
	@param count_of_pages - over how many pages we have to go
	"""
	logger.debug("count_of_pages: %d",count_of_pages)
	positions = [0,1,2,3,4,5,6,7,8,9,10]
	t = tqdm(range(1,count_of_pages+1))
	for i in t: # walk pages
		response = session.content
		#soup = BeautifulSoup(response,"html.parser")
		html_file = str(i)+"_"+case_type+".html"
		if not os.path.exists(os.path.join(html_dir_path,html_file)):
			if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_grwA"):
				extract_data(response,html_file)
		else:
			logger.debug("Skip file '%s'" % html_file)
		
		if i >= 12:
			logger.debug("(%d) - %d < 10 --> %s <== (count_of_pages ) - (i) < 10 = Boolean",(count_of_pages ),(i),(count_of_pages) - i < 10)
			# special compute for last pages
			if (count_of_pages) - (i+1) < 10:
				logger.debug("%d",positions[(i-(count_of_pages))])
				page_number = str(positions[(i-(count_of_pages))]+12)
			else:
				page_number = "12" # next page element has constant ID
		else:
			page_number = str(i+1) # few first pages

		logger.debug("Number = %s",page_number)

		if b_screens:
			session.capture_to(screens_dir_path+"/find_screen_"+case_type+"_0"+str(i)+".png",None,selector="#pagingBox0")

		if session.exists("#_ctl0_ContentPlaceMasterPage__ctl0_pnPaging1_Repeater2__ctl"+page_number+"_LinkButton1") and i+1 < (count_of_pages + 1):
			link_id = "_ctl0_ContentPlaceMasterPage__ctl0_pnPaging1_Repeater2__ctl"+page_number+"_LinkButton1"
			logger.debug("\tClick - Page %d (%s)",(i+1),link_id)
			t.update()
			try:
				result, resources = session.click("#"+link_id, expect_loading=True)
				#session.evaluate("WebForm_DoPostBackWithOptions(new WebForm_PostBackOptions(\"%s\", \"\", true, \"\", \"\", false, true))" % link_id)
				#session.wait_for(page_has_loaded,"Timeout - next page",timeout=main_timeout)
				logger.debug("New page was loaded!")	
			except Exception:
				logger.error("Error (walk_pages) - close browser", exc_info=True)
				logger.debug("error_("+str(i+1)+").png")
				session.capture_to(screens_dir+"/error_("+str(i+1)+").png")
				return False
	return True

def process_court():
	"""
	creates files for processing and saving data, start point for processing
	"""
	d = {"As" : '12', "Ads" : '10', "Afs": '11', "Ars": '116', "Azs": '9'}
	case_types = OrderedDict(sorted(d.items(), key=lambda t: t[0]))
	row_count = 30
	global saved_pages
	saved_pages = 0
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
				session.capture_to(screens_dir_path+"/error_"+case_type+".png")
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
		#	count_of_pages = 5

		result = walk_pages(count_of_pages,case_type)
		saved_pages += count_of_pages
		if result == False:
			logger.warning("Result of 'walk_pages' is False")
			csv_records.close()
			csv_links.close()
			return False
		first_page()
	return True

def main():
	global ghost
	ghost = Ghost()
	global session
	session = ghost.start(download_images=False, show_scrollbars=False, wait_timeout=5000,display=False,plugins_enabled=False)
	logger.info(u"Start - NSS")
	session.open(url)

	if b_screens:
		logger.debug("_screen.png")
		session.capture_to(screens_dir_path+"/_screen.png")
	logger.info("Download data")
	result = process_court()
	#print(result)
	if result == True:
		logger.info("DONE - download")
		logger.debug("Closing browser")
		#session.exit()
		logger.info("Extract informations")
		extract_information()
		logger.info("DONE - extraction")
	else:
		logger.error("Error (main)- closing browser")
		return False
	
	return True

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
	html_dir_path = os.path.join(out_dir,html_dir)

	if not os.path.exists(out_dir):
		os.mkdir(out_dir)
		print("Folder was created '"+out_dir+"'")
	for directory in [documents_dir_path, html_dir_path, txt_dir_path]:
		if not os.path.exists(directory):
			os.mkdir(directory)
			print("Folder was created '"+directory+"'")
	set_logging()
	if b_screens:
		screens_dir_path = os.path.join(out_dir,screens_dir)
		if not os.path.exists(screens_dir_path):
			os.mkdir(screens_dir_path)
			print("Folder was created '"+screens_dir_path+"'")
		logger.debug("Erasing old screens")
		os.system("rm "+os.path.join(screens_dir_path,"*"))
	if options["extraction"]:
		logger.info("Only extract informations")
		extract_information(extract=True)
		logger.info("DONE - extraction")
	else:	
		if main():
			sys.exit(42)
		else:
			sys.exit(-1)