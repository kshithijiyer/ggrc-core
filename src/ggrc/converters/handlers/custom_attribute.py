# Copyright (C) 2016 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Handlers used for custom attribute columns."""

from dateutil.parser import parse

from sqlalchemy import and_

from ggrc import db
from ggrc import models
from ggrc.converters import errors
from ggrc.converters.handlers import handlers

_types = models.CustomAttributeDefinition.ValidTypes


class CustomAttributeColumHandler(handlers.TextColumnHandler):

  """Custom attribute column handler

  This is a handler for all types of custom attribute column. It works with
  any custom attribute definition and with mondatory flag on or off.
  """

  _type_handlers = {
      _types.TEXT: lambda self: self.get_text_value(),
      _types.DATE: lambda self: self.get_date_value(),
      _types.DROPDOWN: lambda self: self.get_dropdown_value(),
      _types.CHECKBOX: lambda self: self.get_checkbox_value(),
      _types.RICH_TEXT: lambda self: self.get_rich_text_value(),
      _types.MAP: lambda self: self.get_person_value(),
  }

  def parse_item(self):
    """Parse raw value from csv file

    Returns:
      CustomAttributeValue with the correct definition type and value.
    """
    self.definition = self.get_ca_definition()
    if self.definition is None:
      self.add_warning(errors.INVALID_ATTRIBUTE_WARNING,
                       column_name=self.display_name)
      return None
    type_ = self.definition.attribute_type.split(":")[0]
    value_handler = self._type_handlers[type_]
    return value_handler(self)

  def get_value(self):
    """Return the value of the custom attrbute field.

    Returns:
      Text representation if the custom attribute value if it exists, otherwise
      None.
    """
    definition = self.get_ca_definition()
    if not definition:
      return ""
    for value in self.row_converter.obj.custom_attribute_values:
      if value.custom_attribute_id == definition.id:
        if value.custom_attribute.attribute_type.startswith("Map:"):
          obj = value.attribute_object
          return getattr(obj, "email", getattr(obj, "slug", None))
        return value.attribute_value
    return None

  def _get_or_create_ca(self):
    ca_definition = self.get_ca_definition()
    if not self.row_converter.obj or not ca_definition:
      return None
    ca = models.CustomAttributeValue.query.filter(and_(
        models.CustomAttributeValue.custom_attribute_id==ca_definition.id,
        models.CustomAttributeValue.attributable_id==self.row_converter.obj.id,
    )).first()
    if ca:
      return ca
    ca = models.CustomAttributeValue(
        custom_attribute=ca_definition,
        custom_attribute_id=ca_definition.id,
        attributable_type=self.row_converter.obj.__class__.__name__,
        attributable_id=self.row_converter.obj.id,
    )
    db.session.add(ca)
    return ca

  def insert_object(self):
    """Add custom attribute objects to db session."""
    if self.dry_run or self.value is None:
      return

    ca = self._get_or_create_ca()
    ca.attribute_value = self.value
    if isinstance(ca.attribute_value, models.mixins.Identifiable):
      obj = ca.attribute_value
      ca.attribute_value = obj.__class__.__name__
      ca.attribute_object_id = obj.id
    self.dry_run = True

  def get_date_value(self):
    """Get date value from input string date."""
    if not self.mandatory and self.raw_value == "":
      return None  # ignore empty fields
    value = None
    try:
      value = parse(self.raw_value)
    except (TypeError, ValueError):
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
    if self.mandatory and value is None:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
    return value

  def get_checkbox_value(self):
    if not self.mandatory and self.raw_value == "":
      return None  # ignore empty fields
    value = self.raw_value.lower() in ("yes", "true")
    if self.raw_value.lower() not in ("yes", "true", "no", "false"):
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
      value = None
    if self.mandatory and value is None:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
    return value

  def get_dropdown_value(self):
    choices_list = self.definition.multi_choice_options.split(",")
    valid_choices = [val.strip() for val in choices_list]
    choice_map = {choice.lower(): choice for choice in valid_choices}
    value = choice_map.get(self.raw_value.lower())
    if value is None and self.raw_value != "":
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
    if self.mandatory and value is None:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
    return value

  def get_text_value(self):
    if not self.mandatory and self.raw_value == "":
      return None  # ignore empty fields
    value = self.clean_whitespaces(self.raw_value)
    if self.mandatory and not value:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
    return value

  def get_rich_text_value(self):
    if not self.mandatory and self.raw_value == "":
      return None  # ignore empty fields
    if self.mandatory and not self.raw_value:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
    return self.raw_value

  def get_person_value(self):
    """Fetch a person based on the email text in column.

    Returns:
        Person model instance
    """
    if not self.mandatory and self.raw_value == "":
      return None  # ignore empty fields
    if self.mandatory and not self.raw_value:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
      return
    value = models.Person.query.filter_by(email=self.raw_value).first()
    if self.mandatory and not value:
      self.add_error(errors.WRONG_VALUE, column_name=self.display_name)
    return value

  def get_ca_definition(self):
    """Get custom attribute definition."""
    cache = self.row_converter.block_converter.get_ca_definitions_cache()
    return cache.get((None, self.display_name))


class ObjectCaColumnHandler(CustomAttributeColumHandler):

  """Handler for object level custom attributes."""

  def set_value(self):
    pass

  def set_obj_attr(self):
    if self.dry_run:
      return
    self.value = self.parse_item()

  def get_ca_definition(self):
    """Get custom attribute definition for a specific object."""
    if self.row_converter.obj.id is None:
      return None
    cad = models.CustomAttributeDefinition
    cache = self.row_converter.block_converter.get_ca_definitions_cache()
    definition = cache.get((self.row_converter.obj.id, self.display_name))
    if not definition:
      definition = cad.query.filter(and_(
          cad.definition_id == self.row_converter.obj.id,
          cad.title == self.display_name
      )).first()
    return definition
