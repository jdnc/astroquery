# Licensed under a 3-clause BSD style license - see LICENSE.rst
import re
from collections import OrderedDict, namedtuple
import tempfile
import warnings
from ..query import BaseQuery
from ..utils.class_or_instance import class_or_instance
from  ..utils import commons
import astropy.units as u
import astropy.coordinates as coord
from astropy.table import Table
try:
    import astropy.io.vo.table as votable
except ImportError:
    import astropy.io.votable as votable
from . import SIMBAD_SERVER, SIMBAD_TIMEOUT, ROW_LIMIT
__all__ = ['Simbad']

# need to fix, before they work
def validate_epoch(func):

    def wrapper(*args, **kwargs):
        if kwargs.get('epoch'):
            value = kwargs['epoch']
            p = re.compile('^[JB]\d+[.]?\d+$', re.IGNORECASE)
            assert p.match(value) is not None
        return func(*args, **kwargs)
    return wrapper

def validate_equinox(func):

    def wrapper(*args, **kwargs):
        if kwargs.get('equinox'):
            value = kwargs['equinox']
            try:
                float(value)
            except ValueError:
                raise("Equinox must be a number")
        return func(*args, **kwargs)
    return wrapper

class Simbad(BaseQuery):
    SIMBAD_URL = 'http://' + SIMBAD_SERVER() + '/simbad/sim-script'
    TIMEOUT = SIMBAD_TIMEOUT()
    WILDCARDS = {
                '*': 'Any string of characters (including an empty one)',
                '?': 'Any character (exactly one character)',
                '[abc]': ('Exactly one character taken in the list. '
                           'Can also be defined by a range of characters: [A-Z]'
                           ),
                '[^0-9]': 'Any (one) character not in the list.'

                }

    # query around not included since this is a subcase of query_region
    _function_to_command = {
                           'query_object_async': 'query id',
                           'query_region_async': 'query coo',
                           'query_catalog_async': 'query cat',
                           'query_bibcode_async': 'query bibcode',
                           'query_bibobj_async': 'query bibobj'
                           }

   # also find a way to fetch the votable fields table from <http://simbad.u-strasbg.fr/simbad/sim-help?Page=sim-fscript#VotableFields>
   # tried something for this in this ipython nb
   # <http://nbviewer.ipython.org/5851110>
    VOTABLE_FIELDS = ['main_id', 'coordinates']

    ROW_LIMIT = ROW_LIMIT()
    @class_or_instance
    def query_object(self, object_name, wildcard=False):
        """
        Queries Simbad for the given object and
        returns the result as an `astropy.table.Table`. Object
        names may also be specified with wildcards. See examples
        below.

        Parameters
        ----------
        object_name : str
            name of object to be queried
        wildcard : boolean, optional
            When it is set to `True` it implies that the object is specified
            with wildcards. Defaults to `False`.

        Returns
        -------
        `astropy.table.Table`
            The results of the query as an `astropy.table.Table`.

        Examples
        --------
        Query Simbad for a given object
        >>> table = Simbad.query_object("m81")

        Query all objects m1 through m9 via a wildcard
        >>> table = Simbad.query_object("m [1-9]", wildcard=True)
        """
        result = self.query_object_async(object_name, wildcard=wildcard)
        return self._parse_result(result)

    @class_or_instance
    def query_object_async(self, object_name, wildcard=False):
        """
        Serves the same function as `astoquery.simbad.Simbad.query_object`. But
        only collects the reponse from the Simbad server and returns.

        Parameters
        ----------
        object_name : str
            name of object to be queried
        wildcard : boolean, optional
            When it is set to `True` it implies that the object is specified
            with wildcards. Defaults to `False`.

        Returns
        -------
        response : `requests.response`
            the response of the query from the server
        """
        request_payload = self._args_to_payload(object_name, wildcard=wildcard,
                                                caller='query_object_async')
        response = commons.send_request(Simbad.SIMBAD_URL, request_payload,
                                Simbad.TIMEOUT)
        return response

    @class_or_instance
    def query_region(self, coordinates, radius=None,
                     equi=None, epoch=None):
        """
        Queries around an object or coordinates as per the specified
        radius and returns the results in an `astropy.table.Table.`

        Parameters
        ----------
        coordinates : str/`astropy.coordinates`
            the identifier or coordinates around which to query.
        radius : str/`astropy.units.Qunatity`, optional
            the radius of the region. If missing, set to default
            value of 20 arcmin.
        equi : float, optional
            the equinox of the coordinates. If missing set to
            default 2000.0.
        epoch : str, optional
            the epoch of the input coordiantes. Must be specified as
            [J|B] <epoch>. If missing, set to default J2000.

        Returns
        -------
        `astropy.table.Table`
            The results of the query as an `astropy.table.Table`.

        Examples
        --------
        Query around an identifier with a cone search radius of 5 degrees
        >>> table = Simbad.query_region("m81", radius=5 * u.deg)
        >>> table = Simbad.query_region("m81", radius="5d0m0s") # a second way

        Query around coordinates
        >>> # String arguments only work for ICRS Coordinates!
        >>> table = Simbad.query_region("00h42m44.3s +41d16m9s", radius="5d0m0s")
        >>> # For other coordinate systems use an astropy.coordinates object:
        >>> table = Simbad.query_region(GalacticCoordinates(-76.22237, 74.49108, unit=(u.degree, u.degree)))

        """
        # if the identifier is given rather than the coordinates, convert to
        # coordinates
        result = self.query_region_async(coordinates, radius=radius,
                                          equi=equi, epoch=epoch)
        return self._parse_result(result)

    @class_or_instance
    def query_region_async(self, coordinates, radius=None, equi=None,
                           epoch=None):
        """
        Serves the same function as `astoquery.simbad.Simbad.query_region`. But
        only collects the reponse from the Simbad server and returns.

        Parameters
        ----------
        coordinates : str/`astropy.coordinates`
            the identifier or coordinates around which to query.
        radius : str/`astropy.units.Qunatity`, optional
            the radius of the region. If missing, set to default
            value of 20 arcmin.
        equi : float, optional
            the equinox of the coordinates. If missing set to
            default 2000.0.
        epoch : str, optional
            the epoch of the input coordiantes. Must be specified as
            [J|B] <epoch>. If missing, set to default J2000.

        Returns
        -------
        response : `requests.response` object
             the response of the query from the server.
        """
        request_payload = self._args_to_payload(coordinates, radius=radius,
                                                equi=equi, epoch=epoch,
                                                caller='query_region_async')
        response = commons.send_request(Simbad.SIMBAD_URL, request_payload,
                                Simbad.TIMEOUT)
        return response

    @class_or_instance
    def query_catalog(self, catalog):
        """
        Queries a whole catalog. Results may be very large
        Number of rows should be controlled by configuring
        `astroquery.simbad.ROW_LIMIT`.

        Parameters
        ----------
        catalog : str
            the name of the catalog.

        Returns
        -------
        `astropy.table.Table`
            The results of the query as an `astropy.table.Table`.

        Examples
        --------
        >>> table = Simbad.query_catalog("m")
        """
        result = self.query_catalog_async(catalog)
        return self._parse_result(result)

    @class_or_instance
    def query_catalog_async(self, catalog):
        """
        Serves the same function as `astoquery.simbad.Simbad.query_catalog`. But
        only collects the reponse from the Simbad server and returns.

        Parameters
        ----------
        catalog : str
            the name of the catalog.

        Returns
        -------
        response : `requests.response` object
             the response of the query from the server.

        """
        request_payload = self._args_to_payload(catalog,
                                                caller='query_catalog_async')
        response = commons.send_request(Simbad.SIMBAD_URL, request_payload,
                                Simbad.TIMEOUT)
        return response

    @class_or_instance
    def query_bibobj(self, bibcode):
        """
        Query all the objects that are contained in the article
        specified by the bibcode, and return results as an `astropy.table.Table`.

        Parameters
        ----------
        bibcode : str
            the bibcode of the article

        Returns
        -------
        `astropy.table.Table`
            The results of the query as an `astropy.table.Table`.

        Examples
        --------
        >>> table = Simbad.query_bibobj("2005A&A.430.165F")

        """
        result = self.query_bibobj_async(bibcode)
        return self._parse_result(result)

    @class_or_instance
    def query_bibobj_async(self, bibcode):
        """
        Serves the same function as `astoquery.simbad.Simbad.query_bibobj`. But
        only collects the reponse from the Simbad server and returns.

        Parameters
        ----------
        bibcode : str
            the bibcode of the article

        Returns
        -------
        response : `requests.response` object
             the response of the query from the server.

        """
        request_payload = self._args_to_payload(
            bibcode, caller='query_bibobj_async')
        response = commons.send_request(Simbad.SIMBAD_URL, request_payload,
                                Simbad.TIMEOUT)
        return response

    @class_or_instance
    def query_bibcode(self, bibcode, wildcard=False):
        """
        Queries the references corresponding to a given bibcode, and
        returns the results in an `astropy.table.Table`. Wildcards
        may be used to specify bibcodes

        Parameters
        ----------
        bibcode : str
            the bibcode of the article
        wildcard : boolean, optional
            When it is set to `True` it implies that the object is specified
            with wildcards. Defaults to `False`.

        Returns
        -------
        `astropy.table.Table`
            The results of the query as an `astropy.table.Table`.

        Examples
        --------
        Fetch all the bibcodes from a given journal for a given year:
        >>> table = Simbad.query_bibcode("2006ApJ*", wildcard=True)

        """
        result = self.query_bibcode_async(bibcode, wildcard=wildcard)
        return self._parse_result(result)

    @class_or_instance
    def query_bibcode_async(self, bibcode, wildcard=False):
        """
        Serves the same function as `astoquery.simbad.Simbad.query_bibcode`. But
        only collects the reponse from the Simbad server and returns.

        Parameters
        ----------
        bibcode : str
            the bibcode of the article
        wildcard : boolean, optional
            When it is set to `True` it implies that the object is specified
            with wildcards. Defaults to `False`.

        Returns
        -------
        response : `requests.response` object
             the response of the query from the server.

        """
        request_payload = self._args_to_payload(bibcode, wildcard=wildcard,
                                                caller='query_bibcode_async', get_raw=True)
        response = commons.send_request(Simbad.SIMBAD_URL, request_payload,
                                Simbad.TIMEOUT)
        return response


    @class_or_instance
    def _args_to_payload(self, *args, **kwargs):
        """
        Takes the arguments from all the query functions
        and returns a dictionary that can be used as the
        data for an HTTP POST request.
        """
        script = ""
        caller = kwargs['caller']
        del kwargs['caller']
        get_raw = kwargs.get('get_raw', False)
        if get_raw:
            del kwargs['get_raw']
        command = self._function_to_command[caller]
        votable_fields = ','.join(Simbad.VOTABLE_FIELDS)
        #if get_raw is set then don't fetch as votable
        votable_def = ("votable {" + votable_fields + "}", "")[get_raw]
        votable_open = ("votable open", "")[get_raw]
        votable_close = ("votable close", "")[get_raw]
        if Simbad.ROW_LIMIT:
            script = "set limit " + str(Simbad.ROW_LIMIT)
        script = "\n".join([script, votable_def, votable_open, command])
        if kwargs.get('wildcard'):
            script += " wildcard"  # necessary to have a space at the beginning
            del kwargs['wildcard']
        # now append args and kwds as per the caller
        # if caller is query_region_async write coordinates as separate ra dec
        if caller == 'query_region_async':
            coordinates = args[0]
            args = args[1:]
            ra, dec, frame = _parse_coordinates(coordinates)
            args = [ra, dec]
            kwargs['frame'] = frame
            if kwargs.get('radius'):
                kwargs['radius'] = _parse_radius(kwargs['radius'])
        args_str = ' '.join([str(val) for val in args])
        # remove default None from kwargs
        # be compatible with python3
        for key in list(kwargs):
            if not kwargs[key]:
                del kwargs[key]
        #join in the order specified otherwise results in error
        all_keys = ['radius', 'frame', 'equi', 'epoch']
        present_keys =[key for key in all_keys if key in kwargs]
        ordered_kwargs = OrderedDict()
        for key in present_keys:
            ordered_kwargs[key] = kwargs[key]
        kwargs_str = ' '.join("{key}={value}".format(key=key, value=value) for
                              key, value in ordered_kwargs.items())
        script += ' '.join([" ", args_str, kwargs_str, "\n"])
        script += votable_close
        return dict(script=script)

    @class_or_instance
    def _parse_result(self, result):

        parsed_result = SimbadResult(result.content)
        try:
            return parsed_result.table
        except Exception:
            warnings.warn("Error in parsing Simbad result. "
                         "Returning raw result instead.")
            return result.content



def _parse_coordinates(coordinates):
    try:
        c = commons.parse_coordinates(coordinates)
        # now c has some subclass of astropy.coordinate
        # get ra, dec and frame
        return _get_frame_coords(c)
    except (u.UnitsException, TypeError):
        raise Exception("Coordinates not specified correctly")


def _get_frame_coords(c):
    if isinstance(c, coord.ICRSCoordinates):
        ra, dec = _to_simbad_format(c.ra, c.dec)
        return (ra, dec, 'ICRS')
    if isinstance(c, coord.GalacticCoordinates):
        ra, dec = (str(c.lonangle.degrees), str(c.latangle.degrees))
        if dec[0] not in ['+', '-']:
            dec = '+' + dec
        return (ra, dec, 'GAL')
    if isinstance(c, coord.FK4Coordinates):
        ra, dec = _to_simbad_format(c.ra, c.dec)
        return (ra, dec,'FK4')
    if isinstance(c, coord.FK5Coordinates):
        ra, dec = _to_simbad_format(c.ra, c.dec)
        return (ra, dec, 'FK5')

def _to_simbad_format(ra, dec):
    ra = ra.format(u.hour, sep=':')
    dec = dec.format(u.hour, sep=':', alwayssign='True')
    return (ra, dec)



def _parse_radius(radius):
    try:
        angle = commons.parse_radius(radius)
    # find the most appropriate unit - d, m or s
        index = min([i for (i,val) in enumerate(angle.dms) if int(val) > 0])
        unit = ('d', 'm', 's')[index]
        if unit == 'd':
            return str(angle.degrees) + unit
        if unit == 'm':
            sec_to_min = angle.dms[2] * u.arcsec.to(u.arcmin)
            total_min = angle.dms[1] + sec_to_min
            return str(total_min) + unit
        if unit == 's':
            return str(angle.dms[2]) + unit
    except (u.UnitsException, coord.UnitsError, AttributeError):
        raise Exception("Radius specified incorrectly")

error_regex = re.compile(r'(?ms)\[(?P<line>\d+)\]\s?(?P<msg>.+?)(\[|\Z)')
bibcode_regex = re.compile(r'query\s+bibcode\s+(wildcard)?\s+([\w]*)')

SimbadError = namedtuple('SimbadError', ('line', 'msg'))
VersionInfo = namedtuple('VersionInfo', ('major', 'minor', 'micro', 'patch'))



class SimbadResult(object):
    __sections = ('script', 'console', 'error', 'data')

    def __init__(self, txt, pedantic=False):
        self.__txt = txt
        self.__pedantic = pedantic
        self.__table = None
        self.__stringio = None
        self.__indexes = {}
        self.exectime = None
        self.sim_version = None
        self.__split_sections()
        self.__parse_console_section()
        self.__warn()
        self.__file = None

    def __split_sections(self):
        for section in self.__sections:
            match = re.search(r'(?ims)^::%s:+?$(?P<content>.*?)(^::|\Z)' % \
                                                        section, self.__txt)
            if match:
                self.__indexes[section] = (match.start('content'),
                                                        match.end('content'))

    def __parse_console_section(self):
        if self.console is None:
            return
        m = re.search(r'(?ims)total execution time: ([.\d]+?)\s*?secs',
                                                                self.console)
        if m:
            try:
                self.exectime = float(m.group(1))
            except:
                # TODO: do something useful here.
                pass
        m = re.search(r'(?ms)SIMBAD(\d) rel (\d)[.](\d+)([^\d^\s])?',
                                                                self.console)
        if m:
            self.sim_version = VersionInfo(*m.groups(None))

    def __warn(self):
        for error in self.errors:
            warnings.warn("Warning: The script line number %i raised "
                            "the error: %s." %\
                            (error.line, error.msg))

    def __get_section(self, section_name):
        if section_name in self.__indexes:
            return self.__txt[self.__indexes[section_name][0]:\
                                    self.__indexes[section_name][1]].strip()

    @property
    def script(self):
        return self.__get_section('script')

    @property
    def console(self):
        return self.__get_section('console')

    @property
    def error_raw(self):
        return self.__get_section('error')

    @property
    def data(self):
        return self.__get_section('data')

    @property
    def errors(self):
        result = []
        if self.error_raw is None:
            return result
        for err in error_regex.finditer(self.error_raw):
            result.append(SimbadError(int(err.group('line')),
                                        err.group('msg').replace('\n', ' ')))
        return result

    @property
    def nb_errors(self):
        if self.error_raw is None:
            return 0
        return len(self.errors)

    @property
    def table(self):
        if self.__file is None:
            self.__file = tempfile.NamedTemporaryFile()
            self.__file.write(self.data.encode('utf-8'))
            self.__file.flush()
            # if bibcode query then first create table from raw data
            bibcode_match = bibcode_regex.search(self.script)
            if bibcode_match:
                self.__table = _create_bibcode_table(self.data, bibcode_match.group(2))
            else:
                self.__table = votable.parse_single_table(self.__file, pedantic=False).to_table()
        return self.__table

def _create_bibcode_table(data, splitter):
    ref_list = [splitter + ref for ref in data.split(splitter)][1:]
    table = Table(names=['References'], dtypes=['object'])
    for ref in ref_list:
        table.add_row([ref.decode('utf-8')])
    return table