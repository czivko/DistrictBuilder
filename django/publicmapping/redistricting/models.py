"""
Define the models used by the redistricting app.

The classes in redistricting.models define the data models used in the 
application. Each class relates to one table in the database; foreign key
fields may define a second, intermediate table to map the records to one
another.

This file is part of The Public Mapping Project
http://sourceforge.net/projects/publicmapping/

License:
    Copyright 2010 Micah Altman, Michael McDonald

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

Author: 
    David Zwarg, Andrew Jennings
"""

from django.contrib.gis.db import models
from django.contrib.gis.geos import MultiPolygon,GEOSGeometry,GEOSException
from django.contrib.auth.models import User
from django.db.models import Sum, Max, Q
from django.db.models.signals import pre_save, post_save
from django.db import connection
from django.forms import ModelForm
from django.conf import settings
from django.utils import simplejson as json
from datetime import datetime
from math import sqrt, pi
from copy import copy

class Subject(models.Model):
    """
    A classification of a set of Characteristics.

    A Subject classifies theC haracteristics of a Geounit. Or, each Geounit
    has one Characteristic per Subject.

    If you think about it in GIS terms: 
        a Geounit is a Feature,
        a Subject is an Attribute on a Geounit, and
        a Characteristic is a Data Value for a Subject.
    """

    # The name of the subject (POPTOT)
    name = models.CharField(max_length=50)

    # The display name of the subject (Total Population)
    display = models.CharField(max_length=200, blank=True)

    # A short display name of the subject (Tot. Pop.)
    short_display = models.CharField(max_length = 25, blank=True)

    # A description of this subject
    description = models.CharField(max_length= 500, blank=True)

    # A flag that indicates if this subject should be displayed.
    is_displayed = models.BooleanField(default=True)

    # The position that this subject should be in, relative to all other
    # Subjects, when viewing the subjects in a list.
    sort_key = models.PositiveIntegerField(default=1)

    # The way this Subject's values should be represented.
    format_string = models.CharField(max_length=50, blank=True)

    class Meta:
        """
        Additional information about the Subject model.
        """

        # The default method of sorting Subjects should be by 'sort_key'
        ordering = ['sort_key']

    def __unicode__(self):
        """
        Represent the Subject as a unicode string. This is the Geounit's 
        display name.
        """
        return self.display

class Geolevel(models.Model):
    """
    A geographic classification for Geounits.

    For example, a Geolevel is the concept of 'Counties', where each 
    Geounit is an instance of a county.  There are many Geounits at a
    Geolevel.
    """

    # The name of the geolevel
    name = models.CharField(max_length = 50)

    def __unicode__(self):
        """
        Represent the Geolevel as a unicode string. This is the Geolevel's 
        name.
        """
        return self.name

class Geounit(models.Model):
    """
    A discrete areal unit.

    A Geounit represents an area at a Geolevel. There are many Geounits at
    a Geolevel. If 'Counties' was a Geolevel, 'Adams County' would be a
    Geounit at that Geolevel.
    """

    # The name of the geounit. If a geounit doesn't have a name (in the
    # instance of a census tract or block), this can be the ID or FIPS code.
    name = models.CharField(max_length=200)

    # The full geometry of the geounit (high detail).
    geom = models.MultiPolygonField(srid=3785)

    # The lite geometry of the geounit (generated from geom via simplify).
    simple = models.MultiPolygonField(srid=3785)

    # The centroid of the geometry (generated from geom via centroid).
    center = models.PointField(srid=3785)

    # The geographic level of this Geounit
    geolevel = models.ForeignKey(Geolevel)

    # Manage the instances of this class with a geographically aware manager
    objects = models.GeoManager()

    @staticmethod
    def get_base_geounits(geounit_ids, geolevel):
        """Get the list of geounits at the base geolevel inside the 
        geometry of geounit_ids.
        
        This method performs a spatial query to find all the small
        Geounits that are contained within the combined extend of the
        Geounits that are in the list of geounit_ids.
        
        The spatial query unionizes the geometry of the geounit_ids,
        simplifies that geometry, then returns all geounits at the base
        geolevel whose centroid falls within the unionized geometry.

        The performance of this method is directly related to the complexity
        of the geometry of the Geounits. This method will perform the best
        on simplified geometry, or geometries with fewer vertices.

        Parameters:
            geounit_ids -- A list of Geounit IDs. Please note that these 
            must be int datatypes, and not str.
            geolevel -- The ID of the Geolevel that contains geounit_ids

        Returns:
            A list of Geounit ids.
        """
        cursor = connection.cursor()

        # craft a custom sql query to get the IDs of the geounits
        cursor.execute('SELECT id from redistricting_geounit where geolevel_id = %s and St_within(center, (select st_simplify(st_union(geom), 10) from redistricting_geounit where geolevel_id = %s and id in %s))', [int(settings.BASE_GEOLEVEL), int(geolevel), geounit_ids])
        results = []
        ids = cursor.fetchall()
        for row in ids:
            results += row
        return results

    @staticmethod
    def get_base_geounits_within(geom):
        """
        Get the  list of geounits at the base geolevel inside a geometry.

        This method performs a spatial query to find all the small
        Geounits that are contained within the geometry provided.

        The spatial query returns all Geounits at the base Geolevel whose
        centroid falls within the geometry.

        The performance of this method is directly related to the complexity
        of the geometry of the Geounits. This method will perform the best
        on simplified geometry, or geometries with fewer vertices.

        Parameters:
            geom -- The GEOSGeometry that describe the limits for the base 
            Geounits.

        Returns:
            A list of Geounit ids.
        """
        cursor = connection.cursor()
        # craft a custom sql query to get the IDs of the geounits
        cursor.execute("select id from redistricting_geounit where geolevel_id = %s and st_within(center, geomfromewkt(%s))",[settings.BASE_GEOLEVEL, str(geom.ewkt)])
        results = []
        ids = cursor.fetchall()
        for row in ids:
            results += row
        return results

    @staticmethod
    def get_mixed_geounits(geounit_ids, geolevel, boundary, inside):
        """
        Spatially search for the largest Geounits inside or outside a 
        boundary.

        Search for Geounits in a multipass search. The searching method
        gets Geounits inside a boundary at a Geolevel, then determines
        if there is a geographic remainder, then repeats the search at
        a smaller Geolevel, until the base Geolevel is reached.

        Parameters:
            geounit_ids -- A list of Geounit IDs. Please note that these
                must be int datatypes, and not str.
            geolevel -- The ID of the Geolevel that contains geounit_ids
            boundary -- The GEOSGeometry that defines the edge of the
                spatial search area.
            inside -- True or False to search inside or outside of the 
                boundary, respectively.

        Returns:
            A list of Geounit objects, with only the ID and Geometry
            fields populated.
        """

        if not boundary and inside:
            # there are 0 geounits inside a non-existant boundary
            return []


        # Make sure the geolevel is a number
        geolevel = int(geolevel)
        levels = Geolevel.objects.all().values_list('id',flat=True).order_by('id')
        selection = None
        units = []
        for level in levels:
            # if this geolevel is the requested geolevel
            if geolevel == level:
                guFilter = Q(id__in=geounit_ids)

                # Get the area defined by the union of the geounits
                selection = Geounit.objects.filter(guFilter).unionagg()
               
                # Begin crafting the query to get the id and geom
                query = "SELECT id,st_ashexewkb(geom,'NDR') FROM redistricting_geounit WHERE id IN (%s) AND " % (','.join(geounit_ids))

                # create a boundary if one doesn't exist
                if not boundary:
                    boundary = empty_geom(selection.srid)
                simple = boundary.simplify(tolerance=100.0,preserve_topology=True)

                if inside:
                    # Searching inside the boundary
                    if level != settings.BASE_GEOLEVEL:
                        # Search by geometry
                        query += "st_within(geom, geomfromewkt('%s'))" % simple.ewkt
                    else:
                        # Search by centroid
                        query += "st_intersects(center, geomfromewkt('%s'))" % simple.ewkt
                else:
                    # Searching outside the boundary
                    if level != settings.BASE_GEOLEVEL:
                        # Search by geometry
                        query += "NOT st_intersects(geom, geomfromewkt('%s'))" % simple.ewkt
                    else:
                        # Search by centroid
                        query += "NOT st_intersects(center, geomfromewkt('%s'))" % simple.ewkt

                # Execute our custom SQL
                cursor = connection.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                count = 0
                for row in rows:
                    count += 1
                    geom = GEOSGeometry(row[1])
                    # Create a geounit, and add it to the list of units
                    units.append(Geounit(id=row[0],geom=geom))

                # if we're at the base level, and haven't collected any
                # geometries, return the units here
                if level == settings.BASE_GEOLEVEL:
                    return units

            # only query geolevels at or below (smaller in size, bigger
            # in id) the geolevel parameter
            elif geolevel < level:
                # union the selected geometries
                union = None
                for selected in units:
                    # this always rebuilds the current extent of all the
                    # selected geounits
                    if union is None:
                        union = selected.geom
                    else:
                        union = union.union(selected.geom)


                # set or merge this onto the existing selection
                if union is None:
                    intersects = selection
                else:
                    intersects = selection.difference(union)

                if inside:
                    # the remainder geometry is the intersection of the 
                    # district and the difference of the selected geounits
                    # and the current extent
                    try:
                        remainder = boundary.intersection(intersects)
                    except GEOSException, ex:
                        # it is not clear what this means, or why it happens
                        remainder = empty_geom(boundary.srid)
                else:
                    # the remainder geometry is the geounit selection 
                    # differenced with the boundary (leaving the 
                    # selection that lies outside the boundary) 
                    # differenced with the intersection (the selection
                    # outside the boundary and outside the accumulated
                    # geometry)
                    try:
                        remainder = selection.difference(boundary)

                        remainder = remainder.intersection(intersects)
                    except GEOSException, ex:
                        # it is not clear what this means, or why it happens
                        remainder = empty_geom(boundary.srid)

                # Check if the remainder is a geometry collection. If it is,
                # munge it into a multi-polygon so that we can use it in our
                # custom sql query
                if remainder.geom_type == 'GeometryCollection' and not remainder.empty:
                    srid = remainder.srid
                    union = None
                    for geom in remainder:
                        mgeom = enforce_multi(geom)
                        if mgeom.geom_type == 'MultiPolygon':
                            if union is None:
                                union = mgeom
                            else:
                                for poly in mgeom:
                                    union.append(poly)
                        else:
                            # do nothing if it's not some kind of poly
                            pass

                    remainder = union
                    if remainder:
                        remainder.srid = srid
                    else:
                        remainder = empty_geom(srid)
                elif remainder.empty or (remainder.geom_type != 'MultiPolygon' and remainder.geom_type != 'Polygon'):
                    remainder = empty_geom(boundary.srid)

                # Check if the remainder is empty -- it may have been 
                # converted, or errored out above, in which case we just
                # have to move on.
                if not remainder.empty:
                    query = "SELECT id,st_ashexewkb(geom,'NDR') FROM redistricting_geounit WHERE geolevel_id = %d AND " % level

                    # Simplify the remainder before performing the query
                    simple = remainder.simplify(tolerance=100.0, preserve_topology=True)

                    if level == settings.BASE_GEOLEVEL:
                        # Query by center
                        query += "st_intersects(center, geomfromewkt('%s'))" % simple.ewkt
                    else:
                        # Query by geom
                        query += "st_within(geom, geomfromewkt('%s'))" % simple.ewkt

                    # Execute our custom SQL
                    cursor = connection.cursor()
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    count = 0
                    for row in rows:
                        count += 1
                        units.append(Geounit(id=row[0],geom=GEOSGeometry(row[1])))

        # Send back the collected Geounits
        return units

    def __unicode__(self):
        """
        Represent the Geounit as a unicode string. This is the Geounit's 
        name.
        """
        return self.name

class Characteristic(models.Model):
    subject = models.ForeignKey(Subject)
    geounit = models.ForeignKey(Geounit)
    number = models.DecimalField(max_digits=12,decimal_places=4)
    percentage = models.DecimalField(max_digits=6,decimal_places=6, null=True, blank=True)
    objects = models.GeoManager()

    def __unicode__(self):
        return u'%s for %s: %s' % (self.subject, self.geounit, self.number)

class Target(models.Model):
    subject = models.ForeignKey(Subject)
    lower = models.PositiveIntegerField()
    upper = models.PositiveIntegerField()

    class Meta:
        ordering = ['subject']

    def __unicode__(self):
        return u'%s : %s - %s' % (self.subject, self.lower, self.upper)

class Plan(models.Model):
    """A plan contains a collection of districts that divide up a state.
    A plan may also be a template, in which case it is usable as a starting
    point by all other users on the system.
    """
    name = models.CharField(max_length=200,unique=True)
    is_template = models.BooleanField(default=False)
    is_shared = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    edited = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User)
    objects = models.GeoManager()

    def __unicode__(self):
        return self.name

    def add_geounits(self, districtid, geounit_ids, geolevel, version):
        """Add the requested geounits to the given district, and remove
        them from whichever district they're currently in. 
        Will return the number of districts effected by the operation.
        """
        
        # incremental is the geometry that is changing
        incremental = Geounit.objects.filter(id__in=geounit_ids).unionagg()

        fixed = 0
        districts = self.get_districts_at_version(int(version))
        for district in districts:
            if district.district_id == int(districtid):
                target = district
                continue

            if not (district.geom and (district.geom.overlaps(incremental) or district.geom.contains(incremental))):
                # if this district does not overlap the selection or
                # if this district does not contain the selection
                if not district.is_latest_version():
                    # if this district has later edits, REVERT them to
                    # this version of the district
                    district_copy = copy(district)
                    district_copy.version = self.version + 1
                    district_copy.id = None
                    district_copy.save()

                    district_copy.clone_characteristics_from(district)

                    fixed += 1

                # go onto the next district
                continue

            # compute the geounits before changing the boundary
            geounits = Geounit.get_mixed_geounits(geounit_ids, geolevel, district.geom, True)
            try:
                geom = district.geom.difference(incremental)
            except GEOSException, ex:
                geom = empty_geom(incremental.srid)

            geom = enforce_multi(geom)

            if not geom.empty:
                district.geom = geom
                simple = geom.simplify(tolerance=100.0,preserve_topology=True)
                district.simple = enforce_multi(simple)
            else:
                district.geom = None
                district.simple = None

            district_copy = copy(district)
            district_copy.version = self.version + 1
            district_copy.id = None
            district_copy.save()

            district_copy.clone_characteristics_from(district)

            if district_copy.delta_stats(geounits,False):
                fixed += 1

        # get the geounits before changing the target geometry
        geounits = Geounit.get_mixed_geounits(geounit_ids, geolevel, target.geom, False)

        if target.geom is None:
            target.geom = enforce_multi(incremental)
        else:
            try:
                union = target.geom.union(incremental)
                target.geom = enforce_multi(union)
            except GEOSException, ex:
                target.geom = None

        if target.geom:
            simple = target.geom.simplify(tolerance=100.0,preserve_topology=True)
            target.simple = enforce_multi(simple)
        else:
            target.simple = None

        target_copy = copy(target)
        target_copy.version = self.version + 1
        target_copy.id = None
        target_copy.save();

        target_copy.clone_characteristics_from(target)

        if target_copy.geom and target_copy.delta_stats(geounits,True):
            fixed += 1

        # save any changes to the version of this plan
        self.version += 1
        self.save()

        return fixed


    def get_wfs_districts(self,version,subject_id):
        """Get the districts in this plan at a specific version. This 
        method behaves much like a WFS service, returning the GeoJSON for
        each district. This is due to the limitations of filtering and the
        complexity of the version query -- it makes it impossible to use
        the WFS layer in Geoserver automatically.
        """
        
        from django.db import connection
        cursor = connection.cursor()

        query = 'SELECT rd.id, rd.district_id, rd.name, lmt.version, rd.plan_id, rc.subject_id, rc.number, st_asgeojson(rd.simple) AS geom FROM redistricting_district rd JOIN redistricting_computedcharacteristic rc ON rd.id = rc.district_id JOIN (SELECT max(version) as version, district_id FROM redistricting_district WHERE plan_id = %d AND version <= %d GROUP BY district_id) AS lmt ON rd.district_id = lmt.district_id WHERE rd.plan_id = %d AND rc.subject_id = %d AND lmt.version = rd.version' % (int(self.id), int(version), int(self.id), int(subject_id))

        cursor.execute(query)
        rows = cursor.fetchall()
        features = []
        for row in rows:
            features.append({ 
                'id': row[0],
                'properties': {
                    'district_id': row[1],
                    'name': row[2],
                    'version': row[3],
                    'number': float(row[6])
                },
                'geometry': json.loads( row[7] )
            })
        return features

    def get_districts_at_version(self, version):
        """Get the districts in this plan at the specified version.
        The districts are versioned to the current plan version when
        they are changed, so this method searches all the districts
        in the plan, returning the districts that have the highest
        version number at or below the version passed in.
        """
        districts = self.district_set.all()
        districts = sorted(list(districts), key=lambda d: d.sortVer())
        dvers = {}
        for i in range(0, len(districts)):
            district = districts[i]
            if district.version > version:
                continue

            dvers[district.district_id] = district

        districts = []
        for value in dvers.itervalues():
            districts.append(value)

        return districts
        

class PlanForm(ModelForm):
    class Meta:
        model=Plan
    

class District(models.Model):
    class Meta:
        ordering = ['name']
    district_id = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=200)
    plan = models.ForeignKey(Plan)
    geom = models.MultiPolygonField(srid=3785, blank=True, null=True)
    simple = models.MultiPolygonField(srid=3785, blank=True, null=True)
    version = models.PositiveIntegerField(default=0)
    objects = models.GeoManager()
    
    
    def sortKey(self):
        """This can be used to sort districts by name, with numbered districts first
        """
        name = self.name;
        if name.startswith('District '):
            name = name.rsplit(' ', 1)[1]
        if name.isdigit():
            return '%03d' % int(name)
        return name 

    def sortVer(self):
        """This method generates a key that is used to sort a list of
        districts first by district_id, then by version number."""
        return self.district_id * 10000 + self.version

    def is_latest_version(self):
        """Determine if this district is the latest version of the district
        stored. If a district is not assigned to a plan, it is always 
        considered the latest version.
        """
        if self.plan:
            qset = self.plan.district_set.filter(district_id=self.district_id)
            maxver = qset.aggregate(Max('version'))['version__max']

            return self.version == maxver
        return true

    def __unicode__(self):
        return self.name

#    def update_stats(self,force=False):
#        """Update the stats for this district, and save them in the
#        ComputedCharacteristic table. This method aggregates the statistics
#        for all the geounits in the mapping table for this district.
#        """
#        all_subjects = Subject.objects.all().order_by('name').reverse()
#        changed = False
#        for subject in all_subjects:
#            computed = self.computedcharacteristic_set.filter(subject=subject).count()
#            if computed > 0 and not force:
#                continue
#
#            if force:
#                my_geounits = Geounit.get_base_geounits_within(self.geom)
#                DistrictGeounitMapping.objects.filter(geounit__in=my_geounits,plan=self.plan).update(district=self)
#            else:
#                my_geounits = DistrictGeounitMapping.objects.filter(district=self).values_list('geounit', flat=True)
#
#            aggregate = Characteristic.objects.filter(geounit__in=my_geounits, subject__exact = subject).aggregate(Sum('number'))['number__sum']
#
#            if aggregate:
#                computed = None
#                if force:
#                    computed = ComputedCharacteristic.objects.filter(subject=subject, district=self)
#                    if computed.count() > 0:
#                        computed.update(number=aggregate)
#                        changed = True
#                    else:
#                        computed = None
#
#                if computed is None:
#                    computed = ComputedCharacteristic(subject = subject, district = self, number = aggregate)
#                    computed.save()
#                    changed = True
#
#        return changed

    def delta_stats(self,geounits,combine):
        """Update the stats for this district incrementally. This method
        iterates over all the computed characteristics and adds or removes
        the characteristic values for the specific geounits only.
        """
        all_subjects = Subject.objects.all()
        changed = False
        for subject in all_subjects:
            aggregate = Characteristic.objects.filter(geounit__in=geounits, subject__exact=subject).aggregate(Sum('number'))['number__sum']
            if aggregate:
                computed = ComputedCharacteristic.objects.filter(subject=subject,district=self)
                if computed:
                    computed = computed[0]
                else:
                    computed = ComputedCharacteristic(subject=subject,district=self,number=0)

                if combine:
                    computed.number += aggregate
                else:
                    computed.number -= aggregate
                computed.save();
                changed = True
        return changed
        

    def get_schwartzberg(self):
        """This is the Schwartzberg measure of compactness, which is the measure of the perimeter of the district 
        to the circumference of the circle whose area is equal to the area of the district
        """
        try:
            r = sqrt(self.geom.area / pi)
            perimeter = 2 * pi * r
            ratio = perimeter / self.geom.length
            return "%.2f%%" % (ratio * 100)
        except:
            return "n/a"

    def is_contiguous(self):
        """Checks to see if the district is contiguous.  The district is already a unioned geom.  Any multipolygon
        with more than one poly in it will not be contiguous.  There is one case where this test may give a false 
        negative - if all of the polys in a multipolygon each meet another poly at one point. In GIS terms, this is
        connected but not contiguous.  But the real-word case may be different.
        http://webhelp.esri.com/arcgisdesktop/9.2/index.cfm?TopicName=Coverage_topology
        """
        if not self.geom == None:
            return len(self.geom) == 1
        else:
            return False

    def clone_characteristics_from(self, origin):
        """Copy the computed characteristics from one district to another.
        This is required when cloning, copying, or instantiating a template
        district.
        """
        cc = ComputedCharacteristic.objects.filter(district=origin)
        for c in cc:
            c.id = None
            c.district = self
            c.save()

    def get_base_geounits_within(self):
        """This will return a list of the geounit ids of the geounits that comprise this district
        at the base level.  We'll check this by seeing whether the centroid of each geounits
        fits within the simplified geometry of this district
        """    
        if not self.simple:
           return list()
        return Geounit.objects.filter(geolevel = settings.BASE_GEOLEVEL, center__within = self.simple).values_list('id')
        


class DistrictGeounitMapping(models.Model):
    district = models.ForeignKey(District)
    geounit = models.ForeignKey(Geounit)
    plan = models.ForeignKey(Plan)
    objects = models.GeoManager()

    def __unicode__(self):
        return "Plan '%s', district '%s': '%s'" % (self.plan.name,self.district.name, self.geounit.name)


class ComputedCharacteristic(models.Model):
    subject = models.ForeignKey(Subject)
    district = models.ForeignKey(District)
    number = models.DecimalField(max_digits=12,decimal_places=4)
    percentage = models.DecimalField(max_digits=6,decimal_places=6, null=True, blank=True)
    objects = models.GeoManager()

    class Meta:
        ordering = ['subject']

class Profile(models.Model):
    user = models.OneToOneField(User)
    organization = models.CharField(max_length=256)
    pass_hint = models.CharField(max_length=256)

def update_profile(sender, **kwargs):
    created = kwargs['created']
    user = kwargs['instance']
    if created:
        profile = Profile(user=user, organization='', pass_hint='')
        profile.save()

post_save.connect(update_profile, sender=User, dispatch_uid="publicmapping.redistricting.User")

#def collect_geom(sender, **kwargs):
#    kwargs['instance'].geom = kwargs['instance'].geounits.collect()

def set_district_id(sender, **kwargs):
    """When a new district is saved, it should get an incremented id that is unique to the plan
    """
    from django.core.exceptions import ValidationError
    district = kwargs['instance']
    if (not district.district_id):
        max_id = District.objects.filter(plan = district.plan).aggregate(Max('district_id'))['district_id__max']
        if max_id:
            district.district_id = max_id + 1
        else:
            district.district_id = 1
        # Unassigned is not counted in MAX_DISTRICTS
        if district.district_id > settings.MAX_DISTRICTS + 1:
            raise ValidationError("Too many districts already.  Reached Max Districts setting")

def update_plan_edited_time(sender, **kwargs):
    district = kwargs['instance']
    plan = district.plan;
    plan.edited = datetime.now()
    plan.save()

pre_save.connect(set_district_id, sender=District)
post_save.connect(update_plan_edited_time, sender=District)

def set_geounit_mapping(sender, **kwargs):
    """When a new plan is saved, all geounits must be inserted into the Unassigned districts and a 
    corresponding set of DistrictGeounitMappings should be applied to it.
    """
    plan = kwargs['instance']
    created = kwargs['created']
    
    if created:
        unassigned = District(name="Unassigned", version = 0, plan = plan)
        unassigned.save()
        
#        # clone all the geounits manually
#        from django.db import connection, transaction
#        cursor = connection.cursor()
#
#        sql = "insert into %s (district_id, geounit_id, plan_id) select %s as district_id, geounit.id as geounit_id, %s as plan_id from %s as geounit where geounit.geolevel_id = %s" % (DistrictGeounitMapping._meta.db_table, unassigned.id, plan.id, Geounit._meta.db_table, settings.BASE_GEOLEVEL)
#        cursor.execute(sql)
#        transaction.commit_unless_managed()

# don't remove the dispatch_uid or this signal is sent twice.
post_save.connect(set_geounit_mapping, sender=Plan, dispatch_uid="publicmapping.redistricting.Plan")

def can_edit(user, plan):
    """Return whether a user can edit the given plan.  They must own it or 
    be a staff member.  Templates cannot be edited, only copied.
    """
    return (plan.owner == user or user.is_staff) and not plan.is_template

def can_view(user, plan):
    """Return whether a user can view a given plan. The plan must have the
    shared flag set.
    """
    return plan.is_shared and not plan.is_template


def can_copy(user, plan):
    """Return whether a user can copy the given plan.  The user must be 
    the owner, or a staff member to copy a plan they own.  Any registered
    user can copy a template.
    """
    return plan.is_template or plan.owner == user or user.is_staff

# this constant is used in places where geometry exceptions occur, or where
# geometry types are incompatible
def empty_geom(srid):
    geom = GEOSGeometry('POINT(0 0)')
    geom = geom.intersection(GEOSGeometry('POINT(1 1)'))
    geom.srid = srid
    return geom

def enforce_multi(geom):
    if geom:
        if geom.geom_type == 'MultiPolygon':
            return geom
        elif geom.geom_type == 'Polygon':
            return MultiPolygon(geom)
        else:
            return empty_geom(geom.srid)
    else:
        return geom
