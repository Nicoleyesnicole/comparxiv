#!/usr/bin/env python

import os
import sys
import arxiv
import requests

from sys import platform
from tqdm import tqdm

version = '0.1.5'
author = 'Timon Emken'
year = '2020'

temp_folder = ".temp_comparxiv/"
def compare_preprints(arxiv_ID, version_a, version_b,keep_temp,show_latex_output,dont_open_pdf,dont_compare_equations):
	check_arguments(arxiv_ID, version_a, version_b)
	print_title(arxiv_ID, version_a, version_b)

	#Check if old or new arxiv ID
	if "/" in arxiv_ID:
		ID_a = os.path.split(arxiv_ID)[-1]+"v"+str(version_a)
		ID_b = os.path.split(arxiv_ID)[-1]+"v"+str(version_b)
	else:
		ID_a = arxiv_ID+"v"+str(version_a)
		ID_b = arxiv_ID+"v"+str(version_b)

	#Create folder for temporary files
	if os.path.exists(temp_folder) == False:
		os.mkdir(temp_folder)

	temp_folder_a = './' + temp_folder + 'temp_' + ID_a+'/'
	temp_folder_b = './' + temp_folder + 'temp_' + ID_b+'/'
	diff_file = os.path.split(arxiv_ID)[-1]+"_v"+str(version_a)+"v"+str(version_b)

	print_paper_information(arxiv_ID,version_a,version_b)

	#1. Download and unpack files
	print("1.) Download and unpack source files:")
	download_from_arxiv(arxiv_ID,version_a)
	download_from_arxiv(arxiv_ID,version_b)

	unpack_source_files(arxiv_ID,version_a,temp_folder_a)
	unpack_source_files(arxiv_ID,version_b,temp_folder_b)

	#2. Identify the .tex and .bbl files.
	#2.1 tex files
	print("\n2.1) Identify master tex files:")
	master_file_a = identify_master_tex_file(temp_folder_a,arxiv_ID)
	master_file_b = identify_master_tex_file(temp_folder_b,arxiv_ID)
	#2.2 bbl files
	print("\n2.2) Identify bbl files:")
	bbl_file_a = identify_bbl_file(temp_folder_a,arxiv_ID)
	bbl_file_b = identify_bbl_file(temp_folder_b,arxiv_ID)

	#3. Latexdiff
	#3.1 tex files 
	print("\n3.1) Run latexdiff on the tex files.")

	latexdiff_command_tex = "latexdiff "
	if show_latex_output == False:
		latexdiff_command_tex += "--ignore-warnings "
	if dont_compare_equations:
		latexdiff_command_tex += "--math-markup=0 "
	
	latexdiff_command_tex += temp_folder_a+master_file_a+" "+temp_folder_b+master_file_b+">"+temp_folder_b+diff_file+".tex"

	os.system(latexdiff_command_tex)

	#3.2 Try to run latexdiff on bbl.
	if bbl_file_a != None and bbl_file_b != None:
		print("\n3.2) Run latexdiff on the bbl files.")
		if show_latex_output == False:
			latexdiff_command_bbl = "latexdiff --ignore-warnings "+temp_folder_a+bbl_file_a+" "+temp_folder_b+bbl_file_b+">"+temp_folder_b+diff_file+".bbl"
		else:
			latexdiff_command_bbl = "latexdiff "+temp_folder_a+bbl_file_a+" "+temp_folder_b+bbl_file_b+">"+temp_folder_b+diff_file+".bbl"
		os.system(latexdiff_command_bbl)

	#4. Run pdflatex
	print("\n4.) Generate a pdf with pdflatex.")
	Generate_PDF(diff_file,temp_folder_b,show_latex_output)

	#5. If unsuccessful, try again with a copy of the version b .bbl file.
	if bbl_file_b != None and os.path.isfile(temp_folder_b+diff_file+".pdf") == False:
		print("\tWarning: No pdf could be generated. Copy the .bbl file of version b and try again.")
		os.system("cp "+ temp_folder_b + bbl_file_b + " " + temp_folder_b + diff_file+".bbl")
		Generate_PDF(diff_file,temp_folder_b,show_latex_output)
	
	success = False;
	if os.path.isfile(temp_folder_b+diff_file+".pdf"):
		success = True
	#6. Compare figures
	# todo

	#7. If successful copy the .pdf.
	if success:
		os.system("mv " +temp_folder_b+diff_file+".pdf" + " ./" + diff_file+".pdf")
		if dont_open_pdf == False:
			if platform == "linux" or platform == "linux2":
				os.system("xdg-open "+diff_file+".pdf")
			elif platform == "darwin":
				os.system("open "+diff_file+".pdf")
		print("\nSuccess!")

	else:
		print("\nFailure! No pdf file could be generated.\nTroubleshooting:")
		print("\t1.) To see more terminal output run:\n\t\t'comparxiv --show_latex_output "+arxiv_ID+" "+str(version_a)+" " + str(version_b) +"'")
		print("\t2.) In some cases latex math environments cause problems with latexdiff. Try running:\n\t\t'comparxiv --dont_compare_equations "+arxiv_ID+" "+str(version_a)+" " + str(version_b) +"'")
	
	#8. Delete temporary files
	if keep_temp == False:
		remove_temporary_files(ID_a)

	return success

def print_paper_information(arxiv_ID,vA,vB):
	papers = arxiv.query(query="",
	    id_list=[arxiv_ID + "v" + str(vA),arxiv_ID + "v" + str(vB)],
	    max_results=2)
	if papers[0].title != papers[1].title:
		print("New title:\t",papers[1].title)
		print("Old title:\t",papers[0].title)
	else:
		print("Title:\t\t",papers[1].title)
	if len(papers[1].authors) == 1:
		print("Author:\t\t",papers[1].authors[0],"\n")
	elif len(papers[1].authors) > 6:
		print("Authors:\t",papers[1].authors[0],"et al.","\n")
	else:
		print("Authors:\t",", " . join(papers[1].authors),"\n")

def check_arguments(arxiv_ID,vA,vB):
	#1. Check for identical versions
	if vA == vB:
		print("Error:\tVersions to compare are identical.")
		os.abort()
	#2. Check if paper exists and has multiple versions.
	latest_version = latest_available_version(arxiv_ID)
	if latest_version == 1:
		print("Error: The paper [%s] has only one version."%(arxiv_ID))
		os.abort()
	#3. Check existence of versions: If none or only one of the versions can be found, generate some meaningful error message.
	papers = arxiv.query(query="",
	    id_list=[arxiv_ID + "v" + str(vA),arxiv_ID + "v" + str(vB)],
	    max_results=2)
	if len(papers) < 2:
		if vA > latest_version and vB > latest_version:
			missing_version = "v%i or v%i"%(vA,vB)
			suggestion_a = latest_version-1
			suggestion_b = latest_version
		elif vA > latest_version:
			missing_version = "v%i"%(vA)
			suggestion_a = latest_version
			if vB == latest_version:
				suggestion_b = vB - 1
			else:
				suggestion_b = vB 
		elif vB > latest_version:
			missing_version = "v%i"%(vB)
			suggestion_b = latest_version
			if vA == latest_version:
				suggestion_a = vA - 1
			else:
				suggestion_a = vA 
		print("Error:\tThe preprint [%s] does not have a version %s. The latest available version is v%i.\n\tTry running 'comparxiv %s %i %i'."%(arxiv_ID,missing_version,latest_version,arxiv_ID,suggestion_a,suggestion_b))
		os.abort()	

def latest_available_version(arxiv_ID):
	papers= arxiv.query(query="",
		id_list=[arxiv_ID],
		max_results=1)
	if len(papers) == 0:
		print("Error: The paper [%s] cannot be found on the preprint server."%(arxiv_ID))
		os.abort()
	version_max = 1
	while version_max < 100:
		paper = arxiv.query(query="",
			id_list=[arxiv_ID+"v"+str(version_max + 1)],
			max_results=1)
		if len(paper) == 0:
			break
		else:
			version_max += 1
	return version_max

def Generate_PDF(file, folder, show_latex_output):
	os.chdir(folder)
	pdflatex_command = "pdflatex -interaction=nonstopmode "+file+".tex"
	if show_latex_output == False:
		pdflatex_command += " 2>&1 > /dev/null"
	os.system(pdflatex_command)
	os.system(pdflatex_command)
	os.chdir("../..")


#Download the files from the preprint server, if it hasn't been done before.
def download_from_url(url, destination):
	file_size = int(requests.head(url).headers["Content-Length"])
	if os.path.exists(destination):
		first_byte = os.path.getsize(destination)
	else:
		first_byte = 0
	if first_byte >= file_size:
		return file_size
	header = {"Range": "bytes=%s-%s" % (first_byte, file_size)}
	pbar = tqdm(
		total=file_size, initial=first_byte,
		unit='B', unit_scale=True, desc=url.split('/')[-1])
	req = requests.get(url, headers=header, stream=True)
	with(open(destination, 'ab')) as f:
		for chunk in req.iter_content(chunk_size=1024):
			if chunk:
				f.write(chunk)
				pbar.update(1024)
	pbar.close()
	return file_size


def download_from_arxiv(arxiv_ID,version):
	#Check if old or new arxiv ID
	if "/" in arxiv_ID:
		filepath = "./"+temp_folder+os.path.split(arxiv_ID)[-1]+"v"+str(version)
		
	else:
		filepath = "./"+temp_folder+arxiv_ID+"v"+str(version)

	if os.path.isfile(filepath) == False:
		url="https://arxiv.org/src/"+arxiv_ID+"v"+str(version)
		download_from_url(url,filepath)
	else:
		print("Download of source files for "+arxiv_ID+"v"+str(version)+" not necessary.")

#Unpack the archived files to a temporary folder
def unpack_source_files(arxiv_ID,version,path_destination):
	version_ID = arxiv_ID+"v"+str(version)
	#Check if old or new arxiv ID
	if "/" in arxiv_ID:
		path_source = "./"+temp_folder+os.path.split(version_ID)[-1]
	else:
		path_source = "./"+temp_folder+version_ID
	# Create folder for temporary files
	if os.path.isfile(path_source) and os.path.exists(path_destination) == False:
		os.makedirs(path_destination)
	# Unpack files
	os.system('tar -xzf '+path_source +' -C '+ path_destination)

def identify_master_tex_file(path,arxiv_ID):
	master_file = None
	tex_files = []
	files = os.listdir(path)
	for file in files:
		if file.endswith(".tex") and (file.startswith(arxiv_ID) or file.startswith(os.path.split(arxiv_ID)[-1]))== False:
			tex_files.append(file)
	if len(tex_files) > 1:
		for file in tex_files:
			with open(path+file) as f:
				if 'begin{document}' in f.read():
					master_file = file
					break
	elif len(tex_files) == 1:
		master_file = tex_files[0]
	elif len(tex_files) == 0 and len(files)==1:
		os.rename(path + file, path + file + ".tex")
		master_file = file + ".tex"
	if master_file == None:
		print("Error in identify_master_tex_file(): Among the ",len(tex_files)," tex files, no master file could be identified.")
		os.abort()
	else:
		print("\t",arxiv_ID+path[-4:-1],": ",master_file)
		return master_file

def identify_bbl_file(path, arxiv_ID):
	# Possibility a: A .bbl file exists.
	for file in os.listdir(path):
		if file.endswith('.bbl') and not file.startswith(arxiv_ID):
			bbl_file = file
			break
	# Possibility b: No .bbl file exists.
	else:
		bbl_file = None

	print("\t",arxiv_ID+path[-4:-1],": ",bbl_file)
	return bbl_file

def remove_temporary_files(arxiv_ID):
	os.system("rm -r "+ temp_folder)

def print_title(ID,v1,v2):
	asci_title = "                                    __  ___       \n  ___ ___  _ __ ___  _ __   __ _ _ _\ \/ (_)_   __\n / __/ _ \| '_ ` _ \| '_ \ / _` | '__\  /| \ \ / /\n| (_| (_) | | | | | | |_) | (_| | |  /  \| |\ V / \n \___\___/|_| |_| |_| .__/ \__,_|_| /_/\_\_| \_/  \n                    |_|                           \n"
	print(asci_title)
	print("Version ",version,", developed by",author,"("+year+")")
	print("\nCompare [%s]: v%i vs v%i\n"%(ID,v1,v2))

if __name__ == "__main__":
	arxiv_ID = str(sys.argv[1])
	version_a = sys.argv[2]
	version_b = sys.argv[3]
	compare_preprints(arxiv_ID,version_a,version_b)