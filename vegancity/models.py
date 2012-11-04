# Copyright (C) 2012 Steve Lamb

# This file is part of Vegancity.

# Vegancity is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Vegancity is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Vegancity.  If not, see <http://www.gnu.org/licenses/>.

from django.db import models
from django.contrib.auth.models import User

from django.db.models import Q
from django.db.models import Count

import shlex
import itertools
import geocode
import validators
import search
import tracking

#####################################
## HELPER CLASSES
#####################################

class NamedModel(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __unicode__(self):
        return self.name

    class Meta:
        abstract = True

class NamedCreatedModel(NamedModel):
    created = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        abstract = True

#######################################
# SITE CLASSES
#######################################

class VegLevel(NamedModel):
    description = models.TextField()
    super_category = models.CharField(max_length=30,
        choices=(
            ('vegan','Vegan'),
            ('vegetarian','Vegetarian'),
            ('not_veg', 'Not Vegetarian'),
            ('beware','Beware!')))

    def __unicode__(self):
        return "(%s) %s" % (self.super_category, self.description)

class Neighborhood(NamedCreatedModel):
    """Used for tracking what neighborhood a vendor is in."""
    class Meta:
        verbose_name = "Neighborhood"
        verbose_name_plural = "Neighborhoods"
        get_latest_by = "created"
        ordering = ('name',)

class BlogEntry(models.Model):
    "Blog entries. They get entered in the admin."
    title = models.CharField(max_length=255)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User)
    body = models.TextField()

    class Meta:
        ordering = ('-created',)
        verbose_name = "Blog Entry"
        verbose_name_plural = "Blog Entries"
        get_latest_by = "created"

    def __unicode__(self):
        return self.title

    @models.permalink
    def get_absolute_url(self):
        return (reverse('blog_detail'), (str(self.id),))

##########################################
# VENDOR-RELATED MODELS
##########################################

    



class VeganDish(NamedCreatedModel):
    vendor = models.ForeignKey('Vendor')

    class Meta:
        get_latest_by = "created"
        ordering = ('name',)
        verbose_name = "Vegan Dish"
        verbose_name_plural = "Vegan Dishes"

class ReviewManager(models.Manager):
    "Manager class for handling searches by review."


    def pending_approval(self):
        """returns all reviews that are not approved, which are
        otherwise impossible to get in a normal query (for now)."""
        normal_qs = self.get_query_set()
        pending = normal_qs.filter(approved=False)
        return pending


class ApprovedReviewManager(ReviewManager):
    "Manager for approved reviews only."

    def get_query_set(self):
        "Changing initial queryset to ignore approved."
        normal_qs = super(ApprovedReviewManager, self).get_query_set()
        new_qs = normal_qs.filter(approved=True)
        return new_qs


class Review(models.Model):
    "The main class for handling reviews.  More or less requires a vendor."
    
    # CORE FIELDS
    vendor = models.ForeignKey('Vendor')
    author = models.ForeignKey(User)

    # ADMINISTRATIVE FIELDS
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    approved = models.BooleanField(default=False)
    objects = ReviewManager()
    approved_objects = ApprovedReviewManager()

    # DESCRIPTIVE FIELDS
    title = models.CharField(max_length=255, null=True, blank=True)
    food_rating = models.IntegerField(
        "How would you rate the food, overall?",
        choices=tuple((i, i) for i in range(1, 5)), 
        blank=True, null=True,)
    atmosphere_rating = models.IntegerField(
        "How would you rate the atmosphere?",
        choices=tuple((i, i) for i in range(1, 5)), 
        blank=True, null=True,)
    best_vegan_dish = models.ForeignKey('VeganDish', blank=True, null=True)
    unlisted_vegan_dish = models.CharField(
        "Favorite Vegan Dish (if not listed)",
        max_length=100,
        help_text="We'll work on getting it in the database so others know about it!",
        blank=True, null=True)
    suggested_feature_tags = models.CharField(max_length=255, blank=True, null=True)
    suggested_cuisine_tags = models.CharField(max_length=255, blank=True, null=True)
    content = models.TextField(
        "Review", 
        help_text="NOTE: All slanderous reviews will be scrutinized. No trolling!")

    def __unicode__(self):
        return "%s -- %s" % (self.vendor.name, str(self.created))

    def get_absolute_url(self):
        return "/vendors/%d/" % self.vendor.id

    class Meta:
        get_latest_by = "created"
        ordering = ('created',)
        verbose_name = "Review"
        verbose_name_plural = "Reviews"

class VendorManager(models.Manager):
    "Manager class for handling searches by vendor."

    def pending_approval(self):
        """returns all vendors that are not approved, which are
        otherwise impossible to get in a normal query (for now)."""
        normal_qs = super(VendorManager, self).get_query_set()
        pending = normal_qs.filter(approved=False)
        return pending
        

    # This may prove useful later.

    # def tags_search(self, query, initial_queryset=None):
    #     """Search vendors by tag.

    #     Takes a query, breaks it into tokens, searches for tags
    #     that contain the token.  If any of the tokens match any
    #     tags, return all the orgs with that tag."""
    #     tokens = shlex.split(query)
    #     q_builder = Q()
    #     for token in tokens:
    #         q_builder = q_builder | Q(name__icontains=token)
    #     cuisine_tag_matches = CuisineTag.objects.filter(q_builder)
    #     feature_tag_matches = FeatureTag.objects.filter(q_builder)
    #     vendors = set()
    #     for tag in itertools.chain(cuisine_tag_matches, feature_tag_matches):
    #         qs = tag.vendor_set.all()
    #         if initial_queryset:
    #             qs = qs.filter(id__in=initial_queryset)
    #         for vendor in qs:
    #             vendors.add(vendor)
    #     vendor_count = len(vendors)
    #     summary_string = ('Found %d results with tags matching "%s".' 
    #                       % (vendor_count, ", ".join(tokens)))
    #     return {
    #         'count' : vendor_count, 
    #         'summary_statement' : summary_string, 
    #         'vendors':vendors
    #         }


    # This, sadly, had to be done away with.
    # Unfortunately, we don't do name searches
    # in a vacuum, so this code is not so usable.

    # def name_search(self, query, initial_queryset=None):
    #     """Search vendors by name.

    #     Takes a query, breaks it into tokens, searches for names
    #     that contain the token.  If any of the tokens match any
    #     names, return all the orgs with that name."""
    #     tokens = shlex.split(query)
    #     q_builder = Q()
    #     for token in tokens:
    #         q_builder |= Q(name__icontains=token)
    #     vendors = self.filter(q_builder)
    #     if initial_queryset:
    #         vendors = vendors.filter(id__in=initial_queryset)
    #     vendor_count = vendors.count()
    #     summary_string = ('Found %d results where name contains "%s".' 
    #                       % (vendor_count, " or ".join(tokens)))
    #     return {
    #         'count' : vendor_count,
    #         'summary_statement' : summary_string, 
    #         'vendors' : vendors
    #         }

    #TODO - replace with something better!
    def address_search(self, query, initial_queryset=None):
        """ Search vendors by address.

        THIS WILL BE CHANGED SO NOT WRITING DOCUMENTATION."""
        
        if initial_queryset:
            vendors = self.filter(id__in=initial_queryset)
        else:
            vendors = self

        # todo this is a mess!
        geocode_result = geocode.geocode_address(query)
        latitude, longitude, neighborhood = geocode_result
        point_a = (latitude, longitude)

        # TODO test this with a reasonable number of latitudes and longitudes
        lat_flr, lat_ceil, lng_flr, lng_ceil = geocode.bounding_box_offsets(point_a, 0.75)

        vendors_in_box = vendors.filter(latitude__gte=lat_flr,
                                     latitude__lte=lat_ceil,
                                     longitude__gte=lng_flr,
                                     longitude__lte=lng_ceil,)


        vendor_distances = geocode.distances(point_a, 
                                             [(vendor.latitude, vendor.longitude)
                                              for vendor in vendors_in_box])


        vendor_pairs = zip(vendors_in_box, vendor_distances)

        sorted_vendor_pairs = sorted(vendor_pairs, key=lambda pair: pair[1][1])

        vendor_matches = filter(lambda pair: geocode.meters_to_miles(pair[1][1]) <= 0.75,
                                 sorted_vendor_pairs)

        vendors = map(lambda x: x[0], vendor_matches)
            
        vendor_count = len(vendors)
        summary_string = ('Found %d results where address is near "%s".' 
                          % (vendor_count, query))
        # return {
        #     'count' : vendor_count, 
        #     'summary_statement' : summary_string, 
        #     'vendors':vendors
        #     }

        return vendors
    
    def search(self, query, initial_queryset=None):
        # rank the likelihood of different search times
        ranks = search.get_ranks(query)
        presentation_order = (rank[1] for rank in ranks)

        # log the query in the db
        tracking.log_query(query, ranks)

        # execute searches and store them in a hash
        searches = {
            'name' : self.name_search(query, initial_queryset),
            'address' : self.address_search(query, initial_queryset),
            'tags' : self.tags_search(query, initial_queryset),
            }

        # compute the set of all vendors found in the 3 searches
        # todo - optimize?
        vendors = [vendor for vendor in initial_queryset if vendor in 
                   itertools.chain(searches['name']['vendors'], 
                                   searches['address']['vendors'], 
                                   searches['tags']['vendors'])]

        result_set = map(lambda x: searches[x], presentation_order)
        return vendors
    

class ApprovedVendorManager(VendorManager):
    """Manager for approved vendors only.

    Inherits the normal vendor manager."""
    def get_query_set(self):
        normal_qs = super(VendorManager, self).get_query_set()
        new_qs = normal_qs.filter(approved=True)
        return new_qs


class Vendor(NamedCreatedModel):
    "The main class for this application"

    # CORE FIELDS
    address = models.TextField(null=True)
    neighborhood = models.ForeignKey('Neighborhood', blank=True, null=True, editable=False)
    phone = models.CharField(max_length=50, blank=True, null=True,
                             validators = [validators.validate_phone_number])
    website = models.URLField(blank=True, null=True)
    latitude = models.FloatField(default=None, blank=True, null=True, editable=False)
    longitude = models.FloatField(default=None, blank=True, null=True, editable=False)

    # ADMINISTRATIVE FIELDS
    modified = models.DateTimeField(auto_now=True, null=True)
    approved = models.BooleanField(default=False)
    objects = VendorManager()
    approved_objects = ApprovedVendorManager()

    # DESCRIPTIVE FIELDS
    notes = models.TextField(blank=True, null=True,)
    veg_level = models.ForeignKey('VegLevel',
        help_text="How vegan friendly is this place?  See documentation for guildelines.",
        blank=True, null=True,)
    cuisine_tags = models.ManyToManyField('CuisineTag', null=True, blank=True)
    feature_tags = models.ManyToManyField('FeatureTag', null=True, blank=True)


    def needs_geocoding(self):
        """Returns true if the vendor is eligible for geocoding,
        but is missing geocoding data."""
        if self.latitude or self.longitude or self.neighborhood:
            return False

        elif not self.address:
            return False

        else:
            return True

    def apply_geocoding(self):

        geocode_result  = geocode.geocode_address(self.address)
        latitude, longitude, neighborhood = geocode_result

        if neighborhood:
            neighborhood_obj = None
            try:
                neighborhood_obj = Neighborhood.objects.get(name=neighborhood)
            except:
                pass

            if not neighborhood_obj:
                    neighborhood_obj = Neighborhood()
                    neighborhood_obj.name = neighborhood
                    neighborhood_obj.save()

            self.neighborhood = neighborhood_obj

        self.latitude = latitude
        self.longitude = longitude


    def save(self, *args, **kwargs):
        """Steps to take before/after saving to db.

        Before saving, see if the vendor has been geocoded.
        If not, geocode."""
        if self.pk is not None:
            orig_address = Vendor.objects.get(pk=self.pk).address
        else:
            orig_address = None
        if (orig_address != self.address) or self.needs_geocoding():
            self.apply_geocoding()
        super(Vendor, self).save(*args, **kwargs)

    def best_vegan_dish(self):
        "Returns the best vegan dish for the vendor"
        dishes = VeganDish.objects.filter(vendor=self)
        if dishes:
            return max(dishes, key=lambda d: Review.objects.filter(best_vegan_dish=d).count())
        else:
            return None

    def food_rating(self):
        reviews = Review.objects.filter(vendor=self)
        food_ratings = [review.food_rating for review in reviews if review.food_rating]
        if food_ratings:
            return sum(food_ratings) / len(food_ratings)
        else:
            return None

    def atmosphere_rating(self):
        reviews = Review.objects.filter(vendor=self)
        atmosphere_ratings = [review.atmosphere_rating for review in reviews if review.atmosphere_rating]
        if atmosphere_ratings:
            return sum(atmosphere_ratings) / len(atmosphere_ratings)
        else:
            return None

    def get_absolute_url(self):
        return "/vendors/%d/" % self.id

    class Meta:
        get_latest_by = "created"
        ordering = ('created',)
        verbose_name = "Vendor"
        verbose_name_plural = "Vendors"

#######################################
# TAG MODEL CLASSES
#######################################

class TagManager(models.Manager):

    def word_search(self, word):
        "takes a word and searches all tag names for that word"
        print "word:", word, "\n"
        qs = self.filter(name__icontains=word)
        return qs

    def with_vendors(self):
        "filters tags to tags that actually have vendors"
        annotated = self.annotate(num_vendors=Count('vendor'))
        qs = annotated.filter(num_vendors__gte=1)
        return qs

    def get_vendors(self, qs):
        results = set()
        for tag in qs:
            results = results.union(tag.vendor_set.all())
        return results
        
class _TagModel(models.Model):
    name = models.CharField(
        help_text="short name, all lowercase alphas, underscores for spaces",
        max_length=255, unique=True
        )
    description = models.CharField(
        help_text="Nicely formatted text.  About a sentence.",
        max_length=255
        )
    created = models.DateTimeField(auto_now_add=True, null=True)
    objects = TagManager()

    def __unicode__(self):
        return self.description

    def get_vendors(self):
        "returns all the vendors that are tagged with this tag."
        return self.vendor_set.all()
   
    class Meta:
        abstract = True
        get_latest_by = "created"
        ordering = ('name',)

class CuisineTag(_TagModel):

    class Meta(_TagModel.Meta):
        verbose_name = "Cuisine Tag"
        verbose_name_plural = "Cuisine Tags"

class FeatureTag(_TagModel):
    
    class Meta(_TagModel.Meta):
        verbose_name = "Feature Tag"
        verbose_name_plural = "Feature Tags"

