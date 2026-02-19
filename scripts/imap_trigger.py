import imaplib
import email
from email.header import decode_header
import base64
from bs4 import BeautifulSoup
import re
import getpass
import os
import sys

detach_dir = '.'
if 'attachments' not in os.listdir(detach_dir):
    os.mkdir('attachments')

mail_pass = "SwkRE4PrSwkRE4P"
username = "StryginaVM@uktaif.ru"
imap_server = "ukexch.uktaif.ru"
imap = imaplib.IMAP4_SSL(imap_server)
imap.login(username, mail_pass)
imap.select('INBOX')
typ, messageParts = imap.fetch(b'5','(RFC822)')
emailBody = messageParts[0][1]
raw_email_string = emailBody.decode('utf-8')

mail = email.message_from_string(raw_email_string)#
print('emailbody complete ...')
for part in mail.walk():
    if part.get_content_maintype() == 'multipart':
        continue
    if part.get('Content-Disposition') is None:
        continue
    fileName = part.get_filename()
    print('file names processed ...')
    if bool(fileName):
        filePath = os.path.join(detach_dir, 'attachments', fileName)
        if not os.path.isfile(filePath):
            print(fileName)
            fp = open(filePath, 'wb')
            fp.write(part.get_payload(decode=True))
            fp.close()
            print('fp closed ...')

