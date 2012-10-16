from django.db.models.sql.query import Query
from django.db.models.sql.compiler import SQLCompiler

def get_default_columns(self, with_aliases=False, col_aliases=None,
            start_alias=None, opts=None, as_pairs=False, local_only=False):
    """
    Computes the default columns for selecting every field in the base
    model. Will sometimes be called to pull in related models (e.g. via
    select_related), in which case "opts" and "start_alias" will be given
    to provide a starting point for the traversal.

    Returns a list of strings, quoted appropriately for use in SQL
    directly, as well as a set of aliases used in the select statement (if
    'as_pairs' is True, returns a list of (alias, col_name) pairs instead
    of strings as the first component and None as the second component).
    """
    result = []
    if opts is None:
        opts = self.query.model._meta
    # Skip all proxy to the root proxied model
    opts = opts.concrete_model._meta
    qn = self.quote_name_unless_alias
    qn2 = self.connection.ops.quote_name
    aliases = set()
    only_load = self.deferred_to_columns()

    if start_alias:
        seen = {None: start_alias}
    for field, model in opts.get_fields_with_model():
        if local_only and model is not None:
            continue
        if start_alias:
            try:
                alias = seen[model]
            except KeyError:
                link_field = opts.get_ancestor_link(model)
                alias = self.query.join((start_alias, model._meta.db_table,
                        link_field.column, model._meta.pk.column))
                seen[model] = alias
        else:
            # If we're starting from the base model of the queryset, the
            # aliases will have already been set up in pre_sql_setup(), so
            # we can save time here.
            alias = self.query.included_inherited_models[model]
        table = self.query.alias_map[alias][1]
        if table in only_load and field.column not in only_load[table]:
            continue
        if as_pairs:
            result.append((alias, field.column))
            aliases.add(alias)
            continue
        if with_aliases and field.column in col_aliases:
            c_alias = 'Col%d' % len(col_aliases)
            result.append('%s.%s AS %s' % (qn(alias),
                qn2(field.column), c_alias))
            col_aliases.add(c_alias)
            aliases.add(c_alias)
        else:
            r = '%s.%s' % (qn(alias), qn2(field.column))
            result.append(r)
            aliases.add(r)
            if with_aliases:
                col_aliases.add(field.column)
    return result, aliases

SQLCompiler.get_default_columns = get_default_columns

def setup_inherited_models(self):
    """
    If the model that is the basis for this QuerySet inherits other models,
    we need to ensure that those other models have their tables included in
    the query.

    We do this as a separate step so that subclasses know which
    tables are going to be active in the query, without needing to compute
    all the select columns (this method is called from pre_sql_setup(),
    whereas column determination is a later part, and side-effect, of
    as_sql()).
    """
    # Skip all proxy models
    opts = self.model._meta.concrete_model._meta
    root_alias = self.tables[0]
    seen = {None: root_alias}

    for field, model in opts.get_fields_with_model():
        if model not in seen:
            link_field = opts.get_ancestor_link(model)
            seen[model] = self.join((root_alias, model._meta.db_table,
                    link_field.column, model._meta.pk.column))
    self.included_inherited_models = seen

Query.setup_inherited_models = setup_inherited_models
