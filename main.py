import tornado.ioloop
import tornado.web as web
import tornado.escape
import tornado.template
import tornado.httputil
import tornado.httpclient
import tornado.auth
import httplib
import tornado.options
from tornado.escape import url_escape, url_unescape

import json
import urllib

import uuid
import base64
import hashlib

import datetime
import time
import email.utils
import os

import re

import gzip
import cStringIO

import model

tornado.options.define("port", default=8111, help="the port number to run on", type=int)

import config

def random256() :
    return base64.b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes)

try :
    cookie_secret = config.cookie_secret
except :
    cookie_secret = None
if not cookie_secret :
    cookie_secret = random256()


model.db_connect("notes.db")
u = model.User.ensure('kmill31415@gmail.com')
w = model.Wiki.ensure("math")
w.add_user(u)

class NRequestHandler(web.RequestHandler) :
    def get_current_user(self) :
        return model.User.with_email(self.get_secure_cookie("user_email"))

class GoogleHandler(NRequestHandler) :
    @tornado.web.asynchronous
    def get(self):
        if self.get_argument("state", None) == self.get_secure_cookie("oauth_state") != None :
            self._on_auth()
            return
        state = json.dumps({"code" : random256(),
                            "redirect" : self.get_argument("next", "/")})
        self.set_secure_cookie("oauth_state", state)
        args = {
            "response_type" : "code",
            "client_id" : config.client_id,
            "redirect_uri" : config.login_url,
            "scope" : "openid email",
            "access_type" : "online",
            "approval_prompt" : "auto",
            "state" : state
            }
        url = "https://accounts.google.com/o/oauth2/auth"
        self.redirect(url + "?" + urllib.urlencode(args))

    def _on_auth(self) :
        if self.get_argument("error", None) :
            raise tornado.web.HTTPError(500, self.get_argument("error"))
        code = self.get_argument("code")

        args = {
            "code" : code,
            "client_id" : config.client_id,
            "client_secret" : config.client_secret,
            "redirect_uri" : config.login_url,
            "grant_type" : "authorization_code"
            }

        tornado.httpclient.AsyncHTTPClient().fetch("https://accounts.google.com/o/oauth2/token", self._on_token, method="POST", body=urllib.urlencode(args))
    def _on_token(self, response) :
        if response.error :
            raise tornado.web.HTTPError(500, "Getting tokens failed")
        data = json.loads(response.body)
        self.access_data = data
        #print "data", data

        headers = tornado.httputil.HTTPHeaders({
                "Authorization" : "Bearer " + data['access_token']
                })
        tornado.httpclient.AsyncHTTPClient().fetch("https://www.googleapis.com/userinfo/v2/me", headers=headers, callback=self.on_userinfo)
    def on_userinfo(self, response) :
        if response.error :
            raise tornado.web.HTTPError(500, "Getting user info failed")
        data = json.loads(response.body)

        email = data["email"]
        access_token = self.access_data["access_token"]
        expires = datetime.datetime.utcnow() + datetime.timedelta(seconds=int(self.access_data["expires_in"]))
        refresh_token = self.access_data.get("refresh_token", None)

#        u = model.User.ensure(email)
        u = model.User.with_email(email)

        self.set_secure_cookie("user_email", u.email)

        state = json.loads(self.get_secure_cookie("oauth_state"))
        self.clear_cookie("oauth_state")
        self.redirect(state['redirect'])

class WikiListHandler(NRequestHandler) :
    @tornado.web.authenticated
    def get(self) :
        self.xsrf_token # to generate token
        self.render("wikis.html", wikis=model.Wiki.with_user(self.current_user))

class IndexHandler(NRequestHandler) :
    def get(self) :
        if self.current_user :
            self.redirect("/wikis", permanent=False)
        else :
            self.render("index.html")

class WikiHandler(NRequestHandler) :
    @tornado.web.authenticated
    def get(self, wikiname) :
        wikiname = url_unescape(wikiname)
        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)
        titles = model.Document.titles(w)
        titles = [t.title() for t in titles]
        titles.sort()
        docids = w.document_ids()
        docids = [d for d in docids if not d['title']]
        docids.sort(key=lambda d : -d['modified'])
        self.render("wiki.html", wiki=w, docids=docids, titles=titles)

class ChangesHandler(NRequestHandler) :
    @tornado.web.authenticated
    def get(self, wikiname) :
        offset = self.get_argument('offset', '0')
        num = self.get_argument('num', '50')
        try :
            offset = int(offset)
        except ValueError :
            offset = 0
        try :
            num = int(num)
        except ValueError :
            num = 50

        wikiname = url_unescape(wikiname)
        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)
        changes = model.Changes.changes(w, num, offset)
        self.render("changes.html", wiki=w, changes=changes, num=num, offset=offset)

class RecentPagesHandler(NRequestHandler) :
    @tornado.web.authenticated
    def get(self, wikiname) :
        offset = self.get_argument('offset', '0')
        num = self.get_argument('num', '50')
        try :
            offset = int(offset)
        except ValueError :
            offset = 0
        try :
            num = int(num)
        except ValueError :
            num = 50

        wikiname = url_unescape(wikiname)
        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)
        changes = model.Changes.changes(w, num, offset, newest=True)
        self.render("pages.html", wiki=w, changes=changes, num=num, offset=offset)


class SearchHandler(NRequestHandler) :
    @tornado.web.authenticated
    def get(self, wikiname) :
        q = self.get_argument('q')
        wikiname = url_unescape(wikiname)

        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)

        words = q.lower().split()
        def query(text) :
            for word in words :
                if word and word in text :
                    return True
            return False

        docs = model.Document.search(w, query)

        self.render("search.html", wiki=w, q=q, docs=docs)

class WikiDocHandler(NRequestHandler) :
    @tornado.web.authenticated
    def get(self, wikiname, title) :
        wikiname = url_unescape(wikiname)
        title = url_unescape(title)
        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)

        if title != title.lower().strip() :
            self.redirect("/wiki/" + url_escape(wikiname) + "/title/" + url_escape(title.lower().strip()),
                          permanent=True)
            return

        docs = []
        for row in model.DB.execute("select docid from meta join documents on meta.docid=documents.id where meta.mvalue=? and not deleted",
                                    (title,)) :
            doc = model.Document.with_id(w, row['docid'])
#            store_meta(doc) #TODO:REMOVE
            docs.append(doc)
        titles=model.Document.titles(w)
        mds = [(doc,) + do_markdown(doc, wiki_titles=titles) for doc in docs]
        if not docs :
            self.redirect("/wiki/" + url_escape(wikiname) + "/edit?title=" + url_escape(title.title()),
                          permanent=False)
            return

        links = model.Links.links_to(w, title.lower().strip())
        ltitles = set()
        linkdocs = []
        for link in links :
            ltitle = link.get_meta("title")
            if ltitle :
                ltitles.add(ltitle)
            else :
                linkdocs.append(linkdocs)
        ltitles = [ltitle.title() for ltitle in ltitles]
        ltitles.sort()
        
        self.render("wikipage.html", wiki=w, docs=mds, title=title, backlinks=ltitles)

class DocHandler(NRequestHandler) :
    @tornado.web.authenticated
    def get(self, wikiname, docid=None) :
        wikiname = url_unescape(wikiname)
        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)
        if not docid :
            raise tornado.web.HTTPError(404)
        doc = model.Document.with_id(w, int(docid))
        if doc == None :
            raise tornado.web.HTTPError(404)
#        store_meta(doc) #TODO:REMOVE
        html, meta = do_markdown(doc, wiki_titles=model.Document.titles(w))
        self.render("doc.html", wiki=w, doc=doc, content=html, meta=meta, title=None)
    @tornado.web.authenticated
    def post(self, wikiname, docid=None) :
        wikiname = url_unescape(wikiname)
        content = self.get_argument('content')

        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)

        if docid != None :
            doc = model.Document.with_id(w, int(docid))
            if doc == None :
                raise tornado.web.HTTPError(404)
            v = model.Version.create(w, self.current_user, "text/texdown", content, [doc.version])
            doc.version = v
            doc.deleted = False
            doc.update()
        else :
            v = model.Version.create(w, self.current_user, "text/texdown", content)
            doc = model.Document(wiki=w, version=v)
            doc.update()

        meta = store_meta(doc)

        if 'title' in meta :
            self.redirect('/wiki/' + url_escape(w.name) + '/title/' + url_escape(meta['title']),
                          permanent=False)
        else :
            self.redirect('/wiki/' + url_escape(w.name) + '/doc/' + str(doc.id), permanent=False)

class DocUuidHandler(NRequestHandler) :
    @tornado.web.authenticated
    def head(self, wikiname, method, uuid) :
        self.get(wikiname, method, uuid, include_body=False)

    @tornado.web.authenticated
    def get(self, wikiname, method, uuid, include_body=True) :
        wikiname = url_unescape(wikiname)
        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)

        uuidparts = uuid.split("/",1)
        uuid = uuidparts[0]

        doc = None
        if method == "u" :
            doc = model.Document.with_uuid(w, uuid)
        elif method == "d" :
            doc = model.Document.with_id(w, int(uuid))
        elif method == 'v' :
            version = model.Version.with_id(w, int(uuid))
            if version :
                doc = model.Document(wiki=w, version=version, temp=True)
        if doc == None :
            raise tornado.web.HTTPError(404)
        
        mimeparts = doc.version.mime.split(';',1)
        mime = mimeparts[0].strip()
        filename = None
        if len(mimeparts) > 1 :
            filename = mimeparts[1]
        if len(uuidparts) > 1 :
            filename = uuidparts[1]

        if type(doc.version.content) == buffer :
            content = bytes(doc.version.content)
        else :
            content = doc.version.content.encode('utf-8')

        self.set_header("Content-Type", mime)
        if filename :
            self.set_header("Content-Disposition", "inline; filename=\"" + url_escape(filename) + "\"")
        self.set_header("Content-Length", len(content))
        created = datetime.datetime.utcfromtimestamp(doc.version.created)
        #print 'created',created
        self.set_header("Last-Modified", created)
        ims_value = self.request.headers.get("If-Modified-Since")
        if ims_value is not None :
            date_tuple = email.utils.parsedate(ims_value)
            if_since = datetime.datetime.fromtimestamp(time.mktime(date_tuple))
            if if_since >= created :
                self.set_status(304)
                return
        if not include_body :
            return
        self.write(content)
        self.flush()
        return
    @tornado.web.authenticated
    def post(self, wikiname, method, uuid) :
        wikiname = url_unescape(wikiname)
        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)

        uuid = uuid.split("/", 1)

        if len(self.request.files['file']) > 1 :
            raise tornado.web.HTTPError(500)

        f = self.request.files['file'][0]
        content_type = (f.content_type or "plain/text")
        filename = None
        if len(uuid) > 1 : filename = uuid[1]
        if f.filename : filename = f.filename
        if filename :
            content_type = content_type + ';' + filename
        v = model.Version.create(w, self.current_user, content_type, buffer(f.body))

        if method == "u" :
            doc = model.Document.with_uuid(w, uuid[0])
            if doc == None :
                doc = model.Document(wiki=w, uuid=uuid[0], version=v)
            else :
                doc.version = v
            doc.update()
        elif method == "d" :
            doc = model.Document.with_id(w, int(uuid[0]))
            if doc == None :
                raise tornado.web.HTTPError(500)
            doc.version = v
            doc.update()
        else :
            raise tornado.web.HTTPError(500)

        self.finish({ 'docid' : doc.id })

class VersionHandler(NRequestHandler) :
    @tornado.web.authenticated
    def get(self, wikiname, versionid) :
        wikiname = url_unescape(wikiname)
        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)
        version = model.Version.with_id(w, int(versionid))
        if version == None or w.id != version.wiki.id :
            raise tornado.web.HTTPError(404)
        doc = model.Document(wiki=w, version=version, temp=True)
        html, meta = do_markdown(doc, wiki_titles=model.Document.titles(w))
        self.render("doc.html", wiki=w, doc=doc, content=html, meta=meta, title=None)

class EditDocHandler(NRequestHandler) :
    @tornado.web.authenticated
    def get(self, wikiname, docid=None) :
        wikiname = url_unescape(wikiname)
        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)
        doc = None
        title = None
        if docid :
            doc = model.Document.with_id(w, int(docid))
            if doc == None :
                raise tornado.web.HTTPError(404)
        else :
            title = self.get_argument('title', None)

        ttitle = title
        if doc :
            ttitle = doc.get_meta('title')
        ltitles = set()
        if ttitle :
            links = model.Links.links_to(w, ttitle.lower().strip())
            linkdocs = []
            for link in links :
                ltitle = link.get_meta("title")
                if ltitle :
                    ltitles.add(ltitle)
                else :
                    linkdocs.append(linkdocs)
            ltitles = [ltitle.title() for ltitle in ltitles]
            ltitles.sort()


        self.render("edit.html", wiki=w, doc=doc, title=title, backlinks=ltitles)

class DeleteDocHandler(NRequestHandler) :
    @tornado.web.authenticated
    def get(self, wikiname, docid) :
        wikiname = url_unescape(wikiname)
        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)
        doc = model.Document.with_id(w, int(docid))
        if doc == None :
            raise tornado.web.HTTPError(404)
        self.render("delete.html", wiki=w, doc=doc)
    @tornado.web.authenticated
    def post(self, wikiname, docid) :
        wikiname = url_unescape(wikiname)
        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)
        doc = model.Document.with_id(w, int(docid))
        if doc == None :
            raise tornado.web.HTTPError(404)
        doc.deleted = True
        doc.update()
        self.redirect('/wiki/' + url_escape(w.name) + '/doc/' + str(doc.id), permanent=False)

class UndeleteDocHandler(NRequestHandler) :
    @tornado.web.authenticated
    def get(self, wikiname, docid) :
        wikiname = url_unescape(wikiname)
        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)
        doc = model.Document.with_id(w, int(docid))
        if doc == None :
            raise tornado.web.HTTPError(404)
        doc.deleted = False
        doc.update()
        self.redirect('/wiki/' + url_escape(w.name) + '/doc/' + str(doc.id), permanent=False)

class ForkHandler(NRequestHandler) :
    @tornado.web.authenticated
    def get(self, wikiname, versionid) :
        wikiname = url_unescape(wikiname)
        w = model.Wiki.with_name(wikiname)
        if w == None :
            raise tornado.web.HTTPError(404)
        if not w.allows_user(self.current_user) :
            raise tornado.web.HTTPError(403)
        version = model.Version.with_id(w, int(versionid))
        if version == None :
            raise tornado.web.HTTPError(404)
        doc = model.Document(wiki=w, version=version)
        doc.update()
        self.redirect('/wiki/' + url_escape(w.name) + '/doc/' + str(doc.id), permanent=False)


from markdown import Markdown
import markdown.extensions
import markdown.extensions.headerid
import markdown.extensions.wikilinks
import markdown.extensions.toc
import markdown.extensions.smarty
import mdx_math

def do_markdown(doc, wiki_titles=set()) :
    if doc.version.mime != "text/texdown" :
        if doc.id :
            url = '/wiki/' + url_escape(doc.wiki.name) + '/file/d/' + str(doc.id)
        else :
            url = '/wiki/' + url_escape(doc.wiki.name) + '/file/v/' + str(doc.version.id)
        text = "Download"
        if doc.version.mime.startswith("image/") :
            text = '<img src="' + url + '">'
        return '<a href="' + url + '">' + text + '</a>', {}
    uuid_link_prefix = '/wiki/' + url_escape(doc.wiki.name) + '/file/u/'
    wiki_link_prefix = '/wiki/' + url_escape(doc.wiki.name) + '/title/'

    protocols = {
        'uuid' : lambda protocol, uuid : "/wiki/"+url_escape(doc.wiki.name)+"/file/u/" + uuid,
        'doc' : lambda protocol, docid : "/wiki/"+url_escape(doc.wiki.name)+"/doc/" + docid
        }

    md = Markdown(output_format="html5",
                  lazy_ol=False,
                  link_protocols=protocols,
                  extensions=["markdown.extensions.meta",
                              mdx_math.MathExtension(enable_dollar_delimiter=True),
                              markdown.extensions.toc.TocExtension(title="Table of contents"),
                              "markdown.extensions.footnotes",
                              "markdown.extensions.tables",
                              "markdown.extensions.tables",
                              "markdown.extensions.fenced_code",
                              markdown.extensions.smarty.SmartyExtension(),
                              markdown.extensions.headerid.HeaderIdExtension(level=2),
                              markdown.extensions.wikilinks.WikiLinkExtension(base_url=wiki_link_prefix, end_url="", titles=wiki_titles)
                              ])

    try :
        html = md.convert(doc.version.content)
        return unicode(html), md.Meta
    except Exception as x :
        return "<div class='markdown-parse-error'>" + str(x) + "</div>", {}

def store_meta(doc) :
    _, meta = do_markdown(doc)
    kvs = {}
    for k, v in meta.iteritems() :
        if v and isinstance(v, list) :
            kvs[k.lower().strip()] = unicode(v[0]).lower().strip()
    doc.update_meta(kvs)
    if "wiki_links" in meta :
        doc.update_links({ link.lower().strip() for link in meta['wiki_links']})
    return kvs

class SignoutHandler(NRequestHandler) :
    def get(self) :
        self.clear_cookie("user_email")
        self.redirect("/", permanent=False)



class NApplication(tornado.web.Application) :
    def __init__(self) :
        settings = dict(
            app_title="Notes",
            template_path="templates",
            static_path="static",
            login_url="/login",
            cookie_secret=cookie_secret,
            ui_modules={},
            xsrf_cookies=True,
            debug=True
            )
        
        handlers = [
            (r"/", IndexHandler),
            (r"/wikis/?", WikiListHandler),
            (r"/wiki/([^/]+)/?", WikiHandler),
            (r"/wiki/([^/]+)/title/(.+)", WikiDocHandler),
            (r"/wiki/([^/]+)/doc/(.+)", DocHandler),
            (r"/wiki/([^/]+)/doc/?", DocHandler),
            (r"/wiki/([^/]+)/file/([^/]+)/(.+)", DocUuidHandler),
            (r"/wiki/([^/]+)/version/(.+)", VersionHandler),
            (r"/wiki/([^/]+)/edit/(.+)", EditDocHandler),
            (r"/wiki/([^/]+)/edit/?", EditDocHandler),
            (r"/wiki/([^/]+)/delete/(.+)", DeleteDocHandler),
            (r"/wiki/([^/]+)/undelete/(.+)", UndeleteDocHandler),
            (r"/wiki/([^/]+)/fork/(.+)", ForkHandler),
            (r"/wiki/([^/]+)/changes/?", ChangesHandler),
            (r"/wiki/([^/]+)/recent/?", RecentPagesHandler),
            (r"/wiki/([^/]+)/search/?", SearchHandler),
            (r"/login", GoogleHandler),
            (r"/logout", SignoutHandler),
            ]
        
        tornado.web.Application.__init__(self, handlers, **settings)

if __name__=="__main__" :
    tornado.options.parse_command_line()
    print "Starting Notes..."
    application = NApplication()
    portnum = tornado.options.options.port
    application.listen(portnum)
    print "Listening on port %s" % portnum
    tornado.ioloop.IOLoop.instance().start()
