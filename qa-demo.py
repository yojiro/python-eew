#!/usr/bin/env python2.7
# -*- coding:utf-8 -*-

# sample code for quakealert

'''
 * Copyright (c) 2012, 2013 Yojiro UO <yuo@nui.org>
 *
 * Permission to use, copy, modify, and distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
'''


import logging
import logging.handlers
import os
import re
import sys
import quakealert

def format_code_message(m, locale='ja'):
    if not (locale=='ja' or locale=='en' or locale=='fr' or locale=='kr'):
        logging.error("locale:%s is not yet supported.", locale) 
        return None
    worddict_ja = dict(alert=':第1報', report=':最終報', 
                       areacode='エリアコード', location='"%s" 地下 %skm', 
                       mag='M%s 震源 %s. ', 
                       EMS='予想最大震度 %s', 
                       EMSn='最大震度未確定')
    worddict_en = dict(alert=':First Alert', report=':Final Report', 
                       areacode='AreaCode', location='"%s" under %skm', 
                       mag='M%s at %s. ', 
                       EMS='Estimated max seismic# is %s', 
                       EMSn='Max seismic not yet determind')
    worddict_fr = dict(alert=u':Première alerte', report=u':Dernier rapport', 
                       areacode=u'Code régional', location=u'"%s" prof. %skm', 
                       mag='M%s, %s. ', 
                       EMS=u'Intensité max estimée: %s', 
                       EMSn=u'Intensité max non déterminée')
    worddict_kr = dict(alert=u':초기 경보', report=u':최종 보고', 
                       areacode=u'지역코드', location=u'"%s" 깊이 %skm', 
                       mag=u'M%s, %s. ', 
                       EMS=u'최대 진도 %s 추정', 
                       EMSn=u'최대 진도 현재 미결정')

    worddict={'ja':worddict_ja, 'en':worddict_en,
              'fr':worddict_fr, 'kr':worddict_kr}
    buf = ''
    try:
        buf += "[%s" % (m['timestamp'].strftime('%H:%M:%SJST %b%d'))
    except KeyError:
        buf += "["
    if m['is_last']:
        buf += worddict[locale]['report']
    elif m['is_first']:
        buf += worddict[locale]['alert']
    buf += '] '
    try:
        loc = m['location_str'][locale]['name']
    except (KeyError, TypeError):
        loc = '%s %s' % (worddict[locale]['areacode'], m['location_code'])
    location_str = worddict[locale]['location'] % (loc, m['depth'])
    if len(m['geo']) == 2:
        location_str += ' (%s,%s)'  % (m['geo'][0], m['geo'][1])
    buf += worddict[locale]['mag'] % (m['magnitude'], location_str)
    if m['max_seismic']:
        buf += worddict[locale]['EMS'] % (m['max_seismic'])
    else:
        buf += worddict[locale]['EMSn'] 
    if m['geo']:
        if len(m['geo']) == 2:
            buf += ' [%s,%s]' % (m['geo'][0], m['geo'][1])
    return buf


def main(client):
    MAX_CONN_ERROR = 60 
    MAX_ERROR = 30 

    while(1):
        if client.connect_err_count > MAX_CONN_ERROR:
            logging.critical("connection failed too many times. bye.")
            exit(1)
        if client.err_count > MAX_ERROR:
            logging.error("too many erros in the connection. try reconect")
            client.stop()
            client.err_count = 0
        mesg = client.process()
        if mesg is None:
            continue
        alert = quakealert.QAlert(mesg)
        ts = alert.timestamp()
        if not alert.is_effective():
            logging.info("not effective message (%s) recieved", alert.drill)
        if alert.is_test_message():
            buf = alert.printable_decode_message()
            logging.info("test message recieved:%s", buf.replace('\n', ' ')) 
        elif alert.is_decode_message():
            buf = alert.printable_decode_message()
            logging.info("decode message recieved:%s", buf.replace('\n', ' ')) 
            print "[%s] decode message:" % (ts)
            print buf
        elif alert.is_code_message():
            buf = alert.code_message()
            logging.info("code message recieved:%s",buf) 
            print "[%s] code message: %s" % (ts, buf)
            p = quakealert.Parser(alert.message_type, buf)
            if p.is_first() or p.is_last():
                qa = p.dump()
                for locale in ('ja', 'en', 'fr', 'kr'):
                    buf = format_code_message(qa, locale=locale)
                    logging.info("formatted code message(locale:%s):%s", 
                            locale,buf)
        else:
            logging.info("unknown message type recieved: %s",
                    alert.typestr.encode('hex'))
            logging.info("---raw buffer---\n:%s", alert.dump_rawbuf())

def daemon_process():
    client = quakealert.QAClient('<server IP addr>', <server port>) 

    # initialize logging
    logging.basicConfig(level=logging.DEBUG,
            format="%(asctime)s %(levelname)-8s %(message)s",
            datefmt='%a, %d %b %Y %H:%M:%S',
            filename='/tmp/qa-demo.out')

    main(client)

if __name__ == "__main__":
    from daemon import DaemonContext
    from lockfile.pidlockfile import PIDLockFile

    dc = DaemonContext(
            pidfile = PIDLockFile('/tmp/qa-demo.pid'),
            working_directory = os.getcwd(),
            stdout = open('/tmp/qa-demo-stdout.txt', 'w+'),
            stderr = open('/tmp/qa-demo-stderr.txt', 'w+'))
    with dc:
        daemon_process()
