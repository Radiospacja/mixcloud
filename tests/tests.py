# FIXME: TESTS!!!

import csv
import datetime
import io
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import dateutil.tz
import httpretty

import mixcloud3 as mixcloud
from mixcloud3.mock import MockServer, parse_headers, parse_multipart


def parse_tracklist(s):
    s = s.split("\n")[1:-1]
    reader = csv.reader(s, delimiter="|", quoting=csv.QUOTE_NONE)
    t = [
        mixcloud.Section(
            int(line[0]),
            mixcloud.Track(line[1].strip(), mixcloud.Artist(None, line[2].strip())),
        )
        for line in reader
    ]
    return t


afx = mixcloud.Artist("aphex-twin", "Aphex Twin")
spartacus = mixcloud.User("spartacus", "Spartacus")
partytime = mixcloud.Cloudcast(
    "party-time",
    "Party Time",
    parse_tracklist(
        """
       0 | Samurai (12" Mix)              | Jazztronik
     416 | Refresher                      | Time of your life
     716 | My time (feat. Crystal Waters) | Dutch
    1061 | Definition of House            | Minimal Funk
    1500 | I dont know                    | Mint Royale
    1763 | Thrill Her                     | Michael Jackson
    2123 | Happy (feat.Charlise)          | Elio Isola
    2442 | Dancin                         | Erick Morillo et al
    2738 | All in my head                 | Kosheen
    """
    ),
    ["Funky house", "Funk", "Soul"],
    "Bla bla",
    spartacus,
    datetime.datetime(2009, 8, 2, 16, 55, 1, tzinfo=dateutil.tz.tzutc()),
)
lambiance = mixcloud.Cloudcast(
    "lambiance",
    "L'ambiance",
    parse_tracklist(
        """
     10 | As Serious As Your Life                     | Four Tet
     20 | Dynamic Symmetry                            | BT
     30 | Vessel                                      | Jon Hopkins
     40 | Vordhosbn                                   | Aphex Twin
     50 | Colour Eye                                  | Jon Hopkins
     60 | Flite                                       | The Cinematic Orchestra
     70 | Altibzz                                     | Autechre
     80 | Untitled [SAW2 CD1 Track1] (Four Tet remix) | Aphex Twin
     90 | Angelica                                    | Lamb
    100 | Quixotic                                    | Spartacus
    110 | Monday - Paracetamol                        | Ulrich Schnauss
    120 | Aquarius                                    | Boards of Canada
    130 | Channel 1 Suite                             | The Cinematic Orchestra
    """
    ),
    ["Idm", "Originals", "Ambient"],
    "Bla bla bla",
    spartacus,
    datetime.datetime(2010, 3, 11, 21, 53, 8, tzinfo=dateutil.tz.tzutc()),
)


class TestMixcloud(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        httpretty.enable()

    def setUp(self):
        self.client_id = "qwerty"
        self.client_secret = "ytrewq"
        self.redirect_uri = "http://localhost/mixcloud-callback"
        self.o = mixcloud.MixcloudOauth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
        )
        self.m = mixcloud.Mixcloud()
        httpretty.reset()
        self.mc = MockServer()

    def testArtist(self):
        self.mc.register_artist(afx)
        resp = self.m.artist("aphex-twin")
        self.assertEqual(resp.name, "Aphex Twin")

    def testUser(self):
        self.mc.register_user(spartacus)
        resp = self.m.user("spartacus")
        self.assertEqual(resp.name, "Spartacus")

    def testCloudcast(self):
        self.mc.register_cloudcast(spartacus, partytime)
        resp = self.m.user("spartacus")
        cc = resp.cloudcast("party-time")
        self.assertEqual(cc.name, "Party Time")
        secs = cc.sections()
        self.assertEqual(len(secs), 9)
        sec = secs[1]
        self.assertEqual(sec.start_time, 416)
        self.assertEqual(sec.track.name, "Refresher")
        self.assertEqual(sec.track.artist.name, "Time of your life")
        self.assertEqual(cc.tags, ["Funky house", "Funk", "Soul"])
        self.assertEqual(cc.description(), "Bla bla")
        self.assertTrue(cc.picture().startswith("http"))
        self.assertEqual(cc.user.key, "spartacus")
        self.assertEqual(cc.user.name, "Spartacus")

    def testCloudcasts(self):
        self.mc.register_cloudcast(spartacus, partytime)
        resp = self.m.user("spartacus")
        ccs = resp.cloudcasts()
        self.assertEqual(len(ccs), 1)
        cc = ccs[0]
        self.assertEqual(cc.name, "Party Time")

    def testLogin(self):
        self.mc.i_am(spartacus)
        user = self.m.me()
        self.assertEqual(user.key, spartacus.key)
        self.assertEqual(user.name, spartacus.name)

    def testUpload(self):
        self.mc.i_am(spartacus)

        def upload_callback(request, uri, headers):
            data = parse_multipart(request.body)
            self.assertIn("mp3", data)
            self.assertIn("picture", data)
            name = data["name"]
            key = mixcloud.slugify(name)
            sections, tags = parse_headers(data)
            description = data["description"]
            me = self.m.me()
            created_time = datetime.datetime.now()
            cc = mixcloud.Cloudcast(
                key, name, sections, tags, description, me, created_time
            )
            self.mc.register_cloudcast(me, cc)
            return (200, headers, "{}")

        self.mc.handle_upload(upload_callback)
        mp3file = io.StringIO("\x00" * 30)
        picturefile = io.StringIO("\x00" * 30)
        r = self.m.upload(partytime, mp3file, picturefile=picturefile)
        self.assertEqual(r.status_code, 200)
        me = self.m.me()
        cc = me.cloudcast("party-time")
        self.assertEqual(cc.name, "Party Time")
        secs = cc.sections()
        self.assertEqual(len(secs), 9)
        sec = secs[3]
        self.assertEqual(sec.start_time, 1061)
        self.assertEqual(sec.track.name, "Definition of House")
        self.assertEqual(sec.track.artist.name, "Minimal Funk")
        self.assertEqual(cc.tags, ["Funky house", "Funk", "Soul"])
        self.assertEqual(cc.description(), "Bla bla")

    def testCloudcastsSection(self):
        self.mc.register_cloudcast(spartacus, partytime)
        u = self.m.user("spartacus")
        ccs = u.cloudcasts()
        cc = ccs[0]
        secs = cc.sections()
        self.assertEqual(secs[7].track.name, "Dancin")

    def testCloudcastsDescription(self):
        self.mc.register_cloudcast(spartacus, partytime)
        u = self.m.user("spartacus")
        ccs = u.cloudcasts()
        cc = ccs[0]
        self.assertEqual(cc.description(), "Bla bla")

    def testLimit(self):
        self.mc.register_cloudcasts(spartacus, [partytime, lambiance])
        u = self.m.user("spartacus")
        ccs = u.cloudcasts()
        self.assertEqual(len(ccs), 2)
        ccs = u.cloudcasts(limit=1)
        self.assertEqual(len(ccs), 1)
        self.assertEqual(ccs[0].key, "party-time")
        ccs = u.cloudcasts(offset=1)
        self.assertEqual(len(ccs), 1)
        self.assertEqual(ccs[0].key, "lambiance")

    def testYaml(self):
        self.mc.i_am(spartacus)
        self.mc.mock_upload(self.m.me())
        mp3file = io.StringIO("\x00" * 30)
        with open("tests/example.yml") as f:
            self.m.upload_yml_file(f, mp3file)
        u = self.m.user("spartacus")
        ccs = u.cloudcasts()
        self.assertEqual(len(ccs), 1)
        cc = ccs[0]
        sections = cc.sections()
        self.assertEqual(len(sections), 16)
        section = sections[6]
        self.assertEqual(section.start_time, 688)
        self.assertEqual(section.track.artist.name, "Menelik & No Se")
        self.assertEqual(section.track.name, "Quelle aventure")
        tags = ["Sample chain", "Samples", "Hip hop", "Pop"]
        self.assertEqual(cc.tags, tags)
        self.assertIn("In this mix we jump", cc.description())

    def testOauthUrl(self):
        full_url = self.o.authorize_url()
        # Check URL without parameters.
        self.assertEqual(full_url.split("?")[0], mixcloud.OAUTH_ROOT + "/authorize")
        # Check query string parameters.
        u = urlsplit(full_url)
        params = parse_qs(u.query)
        self.assertEqual(params["client_id"][0], self.client_id)
        self.assertEqual(params["redirect_uri"][0], self.redirect_uri)

    def testOauthExchange(self):
        self.mc.oauth_exchange()
        access_token = self.o.exchange_token("my_code")
        self.assertEqual(access_token, "my_access_token")

    def testOauthExchangeServerFail(self):
        self.mc.oauth_exchange_fail()
        with self.assertRaises(mixcloud.MixcloudOauthError):
            self.o.exchange_token("my_code")

    @mock.patch("netrc.netrc.authenticators")
    @mock.patch("netrc.netrc.__init__")
    def testNetrc(self, netrc_init, netrc_authenticators):
        netrc_init.return_value = None  # Don't blow up when netrc missing.
        netrc_authenticators.return_value = ("", None, "my_access_token")

        m = mixcloud.Mixcloud()
        self.assertEqual(m.access_token, "my_access_token")
