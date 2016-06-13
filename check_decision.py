#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# coding=utf-8

import pandas as pd
from optparse import OptionParser
import json
import os
from os.path import join
import sys
from tqdm import tqdm
import subprocess

def parameters():
	usage = "usage: %prog [options]"
	parser = OptionParser(usage)
	
	parser.add_option("-i","--input-file",action="store",type="string",dest="input",default=None,help="Name of input CSV file")
	parser.add_option("-d","--input-directory",action="store",type="string", dest="dir",default=None,help="Path to input directory")
	parser.add_option("-o","--output-file",action="store",type="string",dest="output",default="tagged_csv.csv",help="Name of output CSV file")
	(options, args) = parser.parse_args()
	options = vars(options)

	print(options)
	return options

def load_data(csv_file):
	data = pd.read_csv(csv_file,sep=";",na_values=['',"nan"])
	return data

def tag_decision():
	data = load_data(join(input_dir,csv_file))

	odmitnuto = data["decision_result"].str.contains("odmítnuto")
	usneseni = data["decision_result"].str.contains("Usnesení")
	zastaveno = data["decision_result"].str.contains("zastaveno")
	rozsudek = data["decision_result"].str.contains("Rozsudek")

	if "nss" in csv_file:
		label = "case_number"
		is_negative = usneseni & odmitnuto
		is_neutral = usneseni & zastaveno
		is_positive = rozsudek & ~odmitnuto
	elif "us" in csv_file:
		label = "ecli"
		is_negative = odmitnuto
		is_neutral = usneseni & zastaveno
		is_positive = rozsudek & ~odmitnuto
	
	subprocess.call("rm "+output_csv)
	is_other = ~is_positive & ~is_neutral & ~is_negative
	frame = data[is_other][[label,"decision_result"]]
	#frame = data[~data["decision_result"].str.contains("Rozsudek|odmítnuto|zastaveno")][[label,"decision_result"]]
	frame["tag"] = "unknown"
	frame.to_csv(output_csv,mode="a",sep=";",encoding="utf-8",index=False)
	for cond, desc in [(is_negative,"negative"),(is_neutral,"neutral"),(is_positive,"positive")]:
		frame = data[cond][[label,"decision_result"]]
		frame["tag"] = desc
		frame.to_csv(output_csv,mode="a",sep=";",encoding="utf-8",index=False,header=False)

def download_pdf(data):
	frame = data[["link","case_number"]].dropna()
	for row in tqdm(frame.itertuples()):
		case_number = row[2]
		file_name = case_number.replace('/','-')+".pdf"
		if not os.path.exists(join(documents_dir_path,file_name)):
			subprocess.call(["curl", row[1], "-o",join(documents_dir_path,file_name),"-s"])

def extract_text():
	if not os.path.exists(temp_dir_path):
		os.mkdir(temp_dir_path)
	for pdf_file in tqdm(os.listdir(documents_dir_path)):
		txt_file = pdf_file[:-4]+"-text.txt"
		if not os.path.exists(join(txt_dir_path,txt_file)):
			subprocess.call(["pdftotext", "-layout", "%s" % join(documents_dir_path,pdf_file),"%s" % join(txt_dir_path,txt_file)])
			size = os.stat(join(txt_dir_path,txt_file)).st_size
			if size <= 10:
				subprocess.call(["rm", "-f", "%s" % join(txt_dir_path,txt_file)])
				print("OCR extrakce '%s'" % pdf_file)
				txt_file = pdf_file[:-4]+"-text" # tesseract completed automatically ".txt"
				jpg_file = pdf_file[:-4]+".jpg"
				subprocess.call(["convert", "-density", "300", "%s[0]" % join(documents_dir_path,pdf_file),"%s" % join(temp_dir_path,jpg_file)])
				subprocess.call(["tesseract", "%s" % join(temp_dir_path,jpg_file), "%s" % join(txt_dir_path,txt_file), "-l ces" ])

def main():
	if csv_file is not None and input_dir is not None:
		data = load_data(join(input_dir,csv_file))
		if "links" not in csv_file:
			print("Vyhodnocuji případy...")
			tag_decision()		
		else:
			print("Stahuji PDF...")
			download_pdf(data)
			input(":-)")
			print("Extrahuji text...")
			extract_text()
	else:
		print("Nedostatek vstupních parametrů")

if __name__ == "__main__":
	options = parameters()
	csv_file = options["input"]
	output_csv = options["output"]
	input_dir = options["dir"]
	documents_dir_path = join(input_dir,"PDF")
	txt_dir_path = join(input_dir,"TXT")
	temp_dir_path = join(input_dir,"temp")
	main()

