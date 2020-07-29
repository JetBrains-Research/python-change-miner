import json
import os
import smtplib
import re
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import settings

_BASE_URL = settings.get('research_patterns_site_base_url')
_OUT_DIR = settings.get('research_patterns_out_dir')
_DATA_FILE_PATH = os.path.join(_OUT_DIR, 'email-data.json')
_EMAIL_FILE_PATH = os.path.join(_OUT_DIR, 'email-text.html')


def _set_default_if_needed(data, k, v):
    d = data.setdefault(k, v)
    data[k] = d


def _get_sample_info(sample_dir, sample_id):
    with open(os.path.join(sample_dir, f'sample-details-{sample_id}.json'), 'r+') as f:
        sample_info = json.loads(f.read())
    return sample_info


def _load_email_data():
    with open(_DATA_FILE_PATH, 'a+') as f:
        f.seek(0)
        data = f.read()

    try:
        email_data = json.loads(data)
    except:
        email_data = {}

    return email_data


def _save_email_data(email_data):
    with open(_DATA_FILE_PATH, 'w+') as f:
        json.dump(email_data, f, indent=4)


def send_emails(target_emails, payload):
    if not target_emails:
        print('empty target emails')
        return

    with open(_EMAIL_FILE_PATH, 'r+') as f:
        f.seek(0)
        email_text = f.read()

    my_email = settings.get('research_survey_sender_email')
    my_pass = settings.get('research_survey_sender_pass')

    session = smtplib.SMTP('smtp.gmail.com', 587)
    session.starttls()
    session.login(my_email, my_pass)

    disconnected = False
    sent_emails_cnt = 0
    processed_emails = []
    for target_email in target_emails:
        if target_email.endswith('@users.noreply.github.com'):
            logging.warning('Unable to send email to @users.noreply.github.com')
            processed_emails.append(target_email)
            continue

        message = MIMEMultipart()
        message['To'] = target_email
        message['From'] = settings.get('research_survey_email_from')
        message['Subject'] = settings.get('research_survey_email_subject')

        mailing_text = email_text
        for k, v in payload[target_email].items():
            mailing_text = re.sub('{' + k + '}', v, mailing_text)

        message.attach(MIMEText(mailing_text, 'html'))

        text = message.as_string()
        try:
            session.sendmail(my_email, target_email, text)
        except:
            disconnected = True
            logging.exception(f'Unable to send mail to {target_email}, probably, the limit exceeded')
            break

        processed_emails.append(target_email)
        sent_emails_cnt += 1

        print(f'An email was sent from {my_email} to {target_email}')

    if not disconnected:
        session.quit()

    print(f'Done sending emails, processed cnt = {len(processed_emails)}, sent cnt = {sent_emails_cnt}')
    return processed_emails


def start_mailing():
    email_data = _load_email_data()

    target_emails = []
    payload = {}
    for email, author_data in email_data['email_to_author_data'].items():
        if author_data.get('is_sent', False):
            continue

        payload[email] = {
            'name': author_data['author']['name'],
            'url': author_data['url'],
            'base_url': f'{_BASE_URL}/contents.html'
        }
        target_emails.append(email)

    logging.warning(f'Target emails: {len(target_emails)}')

    processed_emails = send_emails(target_emails, payload)
    if not processed_emails:
        return

    for email in processed_emails:
        email_data['email_to_author_data'][email]['is_sent'] = True

    _save_email_data(email_data)
    print('New email_data was saved')


if __name__ == '__main__':
    start_mailing()
