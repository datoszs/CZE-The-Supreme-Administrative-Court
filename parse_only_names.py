#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# coding=utf-8

import os
import re
import codecs
import subprocess
import sys

out_dir = "output_data"
json_dir = "JSON"
txt_dir = "TXT"
txt_dir_path = os.path.join(out_dir,txt_dir)
json_dir_path = os.path.join(out_dir,json_dir)
if not os.path.exists(out_dir):
	print("Neexistuje složka '"+out_dir+"'")
	sys.exit()
else:
	if not os.path.exists(txt_dir_path):
		print("Neexistuje složka '"+txt_dir_path+"'")
		sys.exit()
	else:
		print("Existuje TXT")
	if not os.path.exists(json_dir_path):
		print("Neexistuje složka '"+json_dir_path+"' ... nevadí")	
	else:
		print("Existuje JSON")


soubory = [os.path.join(txt_dir_path,fn) for fn in next(os.walk(txt_dir_path))[2]]
#zbytek = "zbytek.txt"
#soubory = open(zbytek,encoding="utf-8").read().split("\n")
print(len(soubory))
celkem = 0
with open("all_texts.txt","w",encoding='utf-8') as texts:
	for soubor in soubory:
		with codecs.open(soubor,'r',encoding='utf-8') as f:
			
			znacka = f.readline().strip()

			text = f.read()
			texts.write(text+"\n")
			shoda = re.match('.*(([Zzr]as[tr](?!aven[oiá]|upitelstvo|avil?|upov[áa][nt]|avuje|upci)[^,:]+)[,:.]?\s+(advok|se)).*', text, flags=re.DOTALL)
			#[Zzr]ast(\S+|\s+){1,2}\s(\S+)\s[^,]+,\s+(advok|se)
			#[Zzr]as[tr]([^,]+)(?!upitelstv[oa]),\s+(advok|se)
			if shoda is not None:
				celkem += 1
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
						try:
							print("Jméno advokáta (7. pád):","%-15s" % jmeno.split(" ")[0],"%-20s" % jmeno.split(" ")[1],shoda.group(1).replace('\n',' ').replace('\r',''),"<--",os.path.basename(soubor))
						except:
							print(soubor)

print(celkem,"z",len(soubory),"-->",len(soubory)-celkem,"neobsahuje jmeno zastupce")

