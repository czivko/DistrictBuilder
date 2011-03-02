"""
Define the calculators used for scoring in the redistricting app.

The classes in redistricting.calculators define the scoring
calculators used in the application. Each class relates to
one type of calculator that can be referenced within the config
file to define how to score a plan or district.

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
    Andrew Jennings, David Zwarg, Kenny Shepard
"""

from math import sqrt, pi
from django.utils import simplejson as json

class CalculatorBase:
    """
    A base class for all calculators that defines the result object,
    and defines a couple default rendering options for HTML, JSON, and 
    Boolean.
    """

    # This calculator's result
    result = None

    # This calculator's dictionary of arguments. This dictionary is keyed
    # by argument name, and the values are tuples of the type name and
    # the value.
    #
    # E.g.: arg_dict = { 'minimum':('literal','0.5',) }
    #
    arg_dict = {}

    def compute(self, **kwargs):
        """
        Compute the value for this calculator. The base class calculates
        nothing.
        """
        pass

    def html(self):
        """
        Return a basic HTML representation of the result.
        """
        if not self.result is None:
            return '<span>%s</span>' % self.result
        else:
            return '<span>n/a</span>'

    def json(self):
        """
        Return a basic JSON representation of the result.
        """
        return json.dumps( {'result':self.result} )

    def get_value(self, argument, district=None):
        """
        Get the value of an argument if it is a literal or a subject.
        """
        (argtype, argval) = self.arg_dict[argument]
        if argtype == 'literal':
            return argval
        elif argtype == 'subject' and not district is None:
            # This method is more fault tolerant than _set.get, since it 
            # won't throw an exception if the item doesn't exist.
            cc = district.computedcharacteristic_set.filter(subject__name=argval)
            if cc.count() == 0:
                return None
            
            return cc[0].number

        return None


class Schwartzberg(CalculatorBase):
    """
    Calculator for the Schwartzberg measure of compactness.
        
    The Schwartzberg measure of compactness measures the perimeter of 
    the district to the circumference of the circle whose area is 
    equal to the area of the district.
    """
    def compute(self, **kwargs):
        """
        Calculate the Schwartzberg measure of compactness. This calculator
        only operates on districts.

        Keywords:
            districts - A list of districts to compute compactness for.
        """
        if not 'district' in kwargs:
            return

        district = kwargs['district']
        if district.geom is None:
            return
        
        r = sqrt(district.geom.area / pi)
        perimeter = 2 * pi * r
        self.result = perimeter / district.geom.length

    def html(self):
        return ("%.2f%%" % (self.result * 100)) if self.result else "n/a"


class Sum(CalculatorBase):
    """
    Sum up all values.
    """
    def __init__(self):
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Calculate the sum of a series of values. Each value to be added
        should be added to the args_dict as 'value1', 'value2', etc.
        """
        districts = []

        if 'district' in kwargs:
            districts = [kwargs['district']]
        elif 'plan' in kwargs:
            plan = kwargs['plan']
            districts = plan.get_districts_at_version(plan.version, include_geom=False)

        else:
            return

        self.result = 0

        for district in districts:
            argnum = 1
            while ('value%d'%argnum) in self.arg_dict:
                number = self.get_value('value%d'%argnum, district)
                if not number is None:
                    self.result += float(number)

                argnum += 1


class Percent(CalculatorBase):
    def __init__(self):
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Calculate a percentage for two values. This calculator requires
        a 'numerator' argument, and a 'denominator' argument.
        """
        district = None

        if 'district' in kwargs:
            district = kwargs['district']

        elif 'plans' in kwargs:
            pass

        else:
            return

        num = self.get_value('numerator',district)
        den = self.get_value('denominator',district)

        if num is None or den is None:
            return

        self.result = float(num) / float(den)


class Threshold(CalculatorBase):
    def __init__(self):
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Calculate and determine if a value exceeds a threshold.
        """
        district = None

        if 'district' in kwargs:
            district = kwargs['district']

        elif 'plans' in kwargs:
            pass

        else:
            return

        val = self.get_value('value',district)
        thr = self.get_value('threshold',district)

        if val is None or thr is None:
            return

        self.result = float(val) > float(thr)


class Range(CalculatorBase):
    def __init__(self):
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Calculate and determine if a value lies within a range.
        """
        district = None

        if 'district' in kwargs:
            district = kwargs['district']

        elif 'plans' in kwargs:
            pass

        else:
            return

        val = self.get_value('value',district)
        minval = self.get_value('min',district)
        maxval = self.get_value('max',district)

        if val is None or minval is None or maxval is None:
            return

        self.result = float(val) > float(minval) and float(val) < float(maxval)
