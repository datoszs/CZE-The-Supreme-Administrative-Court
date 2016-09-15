# The Supreme Administrative Court
Crawler of Czech Republic The Supreme Administrative Court.

Downloads HTML files, PDF files and produces CSV file with results


## Requirements
* beautifulsoup4==4.4.1
* Ghost.py==0.2.3
* pandas==0.18.1
* PySide==1.2.4
* tqdm==4.8.4
* CURL

##Usage

```
Usage: nss-crawler.py [options]

Options:
  -h, --help            show this help message and exit
  -w, --without-download
                        Not download PDF documents
  -n, --not-delete      Not delete working directory
  -d DIR, --output-directory=DIR
                        Path to output directory
  -f DATE_FROM, --date-from=DATE_FROM
                        Start date of range (d. m. yyyy)
  -t DATE_TO, --date-to=DATE_TO
                        End date of range (d. m. yyyy)
  -c, --capture         Capture screenshots?
  -o FILENAME, --output-file=FILENAME
                        Name of output CSV file
  -e, --extraction      Make only extraction without download new data
  ```
