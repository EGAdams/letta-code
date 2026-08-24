"""Edge-case cover for the ICategoryNamer port and its one implementation.

``TaxonomyCategoryNamer`` sits on the path from a stored expense to the Set
Category dropdown, and its failure mode is silence: hand the form a leaf name
instead of a reporting-bucket label and the ``<select>`` just stays blank. So
the tests below pin the *translation contract* -- what comes back for a hit, a
miss, and every shape of junk -- rather than any particular call sequence, and
they exercise it through injected doubles so no database is involved.

The late-binding tests are the load-bearing ones. ``taxonomy_category_namer()``
wires the namer with lambdas so a monkeypatched taxonomy function is honoured
even by the long-lived cached repository; wiring the bare functions instead
would still pass every other test in this file.
"""

import pytest

import server
from finance.category_naming import ICategoryNamer, TaxonomyCategoryNamer


class RecordingTaxonomy:
    """A stand-in taxonomy: fixed answers, plus a log of what it was asked."""

    def __init__(self, labels=None, resolutions=None):
        self.labels = labels or {}
        self.resolutions = resolutions or {}
        self.label_calls = []
        self.resolve_calls = []

    def label_for(self, category_id):
        self.label_calls.append(category_id)
        return self.labels.get(category_id)

    def resolve(self, name):
        self.resolve_calls.append(name)
        return self.resolutions.get(name, (None, None))


def namer_over(taxonomy):
    return TaxonomyCategoryNamer(taxonomy.label_for, taxonomy.resolve)


@pytest.fixture
def taxonomy():
    return RecordingTaxonomy(
        labels={140: 'Office Supplies', 243: 'Rosemary', 0: 'Zero Bucket'},
        resolutions={
            'Office Supplies': (140, 'cat-office'),
            'Rosemary': (243, 'cat-rosemary'),
            # The one selectable name that legitimately resolves to no id.
            'Uncategorized': (None, 'cat-uncategorized'),
        },
    )


# --------------------------------------------------------------------------
# The port itself
# --------------------------------------------------------------------------

def test_implements_the_port():
    assert issubclass(TaxonomyCategoryNamer, ICategoryNamer)


def test_port_cannot_be_instantiated_bare():
    """ICategoryNamer is a port, not a base class with a usable default."""
    with pytest.raises(TypeError):
        ICategoryNamer()


def test_half_an_implementation_is_rejected():
    """Implementing one direction and not the other must not silently work."""

    class Halfway(ICategoryNamer):
        def name_for(self, category_id):
            return ''

    with pytest.raises(TypeError):
        Halfway()


# --------------------------------------------------------------------------
# name_for: id -> label
# --------------------------------------------------------------------------

def test_name_for_returns_the_label(taxonomy):
    assert namer_over(taxonomy).name_for(140) == 'Office Supplies'


def test_name_for_passes_the_id_through_untouched(taxonomy):
    namer_over(taxonomy).name_for(243)
    assert taxonomy.label_calls == [243]


@pytest.mark.parametrize('missing', [None, 999_999, -1, 'nonsense'])
def test_name_for_unknown_id_is_empty_string_not_none(taxonomy, missing):
    """'' is the contract: the caller drops it straight into a form field,
    and a None there renders the literal text "None" in the dropdown."""
    assert namer_over(taxonomy).name_for(missing) == ''


def test_name_for_falsy_label_is_normalised_to_empty_string():
    """A taxonomy that answers None/'' must not leak either shape onward."""
    namer = TaxonomyCategoryNamer(lambda _id: None, lambda _n: (None, None))
    assert namer.name_for(1) == ''


def test_name_for_id_zero_is_looked_up_not_short_circuited(taxonomy):
    """0 is falsy but is still an id; it must reach the taxonomy."""
    assert namer_over(taxonomy).name_for(0) == 'Zero Bucket'
    assert taxonomy.label_calls == [0]


def test_name_for_does_not_swallow_a_taxonomy_failure():
    """A broken taxonomy is a real fault, not an empty label."""

    def boom(_category_id):
        raise RuntimeError('taxonomy unavailable')

    namer = TaxonomyCategoryNamer(boom, lambda _n: (None, None))
    with pytest.raises(RuntimeError):
        namer.name_for(140)


def test_name_for_resolves_per_call(taxonomy):
    """Nothing is memoised: a taxonomy that changes underneath is seen."""
    namer = namer_over(taxonomy)
    assert namer.name_for(140) == 'Office Supplies'
    taxonomy.labels[140] = 'Office Supplies (renamed)'
    assert namer.name_for(140) == 'Office Supplies (renamed)'


# --------------------------------------------------------------------------
# id_for: label -> id
# --------------------------------------------------------------------------

def test_id_for_returns_the_id(taxonomy):
    assert namer_over(taxonomy).id_for('Office Supplies') == 140


@pytest.mark.parametrize('blank', [None, '', '   ', '\t', '\n', '\r\n', ' \t\n '])
def test_id_for_blank_is_none_without_consulting_the_taxonomy(taxonomy, blank):
    """"No category" is a legal edit -- it clears the field, it is not an
    error -- and it must not be sent to the taxonomy to be rejected."""
    assert namer_over(taxonomy).id_for(blank) is None
    assert taxonomy.resolve_calls == []


def test_id_for_strips_surrounding_whitespace(taxonomy):
    assert namer_over(taxonomy).id_for('  Office Supplies\n') == 140
    assert taxonomy.resolve_calls == ['Office Supplies']


def test_id_for_does_not_strip_interior_whitespace(taxonomy):
    """Reporting labels contain spaces; only the edges are noise."""
    assert namer_over(taxonomy).id_for('Office Supplies') == 140


def test_id_for_unknown_name_raises_value_error(taxonomy):
    with pytest.raises(ValueError):
        namer_over(taxonomy).id_for('Not A Real Category')


def test_id_for_error_names_the_offending_value(taxonomy):
    """The message reaches the operator, so it has to say what was rejected."""
    with pytest.raises(ValueError) as excinfo:
        namer_over(taxonomy).id_for('Not A Real Category')
    assert 'Not A Real Category' in str(excinfo.value)
    assert 'category' in str(excinfo.value).lower()


def test_id_for_uncategorized_is_none_and_is_not_an_error(taxonomy):
    """The css class -- not the id -- is what says "this name is selectable".
    'Uncategorized' resolves to (None, 'cat-uncategorized') and clears the id;
    keying the rejection off the id would turn a legal pick into a 400."""
    assert namer_over(taxonomy).id_for('Uncategorized') is None


def test_id_for_rejects_when_class_is_missing_even_if_an_id_came_back():
    """A (id, None) answer means "not selectable" and must still be refused,
    so a half-populated legacy map cannot smuggle a category through."""
    namer = TaxonomyCategoryNamer(lambda _id: '', lambda _n: (7, None))
    with pytest.raises(ValueError):
        namer.id_for('Half Known')


def test_id_for_accepts_an_empty_string_class():
    """'' is a class, however useless -- only None means unselectable."""
    namer = TaxonomyCategoryNamer(lambda _id: '', lambda _n: (7, ''))
    assert namer.id_for('Odd But Selectable') == 7


@pytest.mark.parametrize('weird', [123, 4.5, True])
def test_id_for_coerces_non_string_names_to_text(weird):
    """The name arrives from untrusted JSON; a number must be looked up as
    its text, not blow up with a TypeError inside the taxonomy."""
    seen = []

    def resolve(name):
        seen.append(name)
        return (1, 'cat-x')

    assert TaxonomyCategoryNamer(lambda _id: '', resolve).id_for(weird) == 1
    assert seen == [str(weird)]


@pytest.mark.parametrize('falsy', [False, 0, 0.0, [], {}])
def test_id_for_any_falsy_name_is_treated_as_no_category(falsy):
    """Pinned, because it is a hair off the coercion above: `name or ''` runs
    before str(), so every falsy value clears the field instead of being
    looked up as its text. Only truthy junk reaches the taxonomy."""
    namer = TaxonomyCategoryNamer(lambda _id: '', lambda _n: (1, 'cat-x'))
    assert namer.id_for(falsy) is None


def test_id_for_does_not_swallow_a_taxonomy_failure():
    def boom(_name):
        raise RuntimeError('taxonomy unavailable')

    namer = TaxonomyCategoryNamer(lambda _id: '', boom)
    with pytest.raises(RuntimeError):
        namer.id_for('Office Supplies')


def test_id_for_resolves_per_call(taxonomy):
    namer = namer_over(taxonomy)
    with pytest.raises(ValueError):
        namer.id_for('New Bucket')
    taxonomy.resolutions['New Bucket'] = (500, 'cat-new')
    assert namer.id_for('New Bucket') == 500


def test_round_trip_between_the_two_directions(taxonomy):
    namer = namer_over(taxonomy)
    assert namer.name_for(namer.id_for('Office Supplies')) == 'Office Supplies'


# --------------------------------------------------------------------------
# The composition root in server.py
# --------------------------------------------------------------------------

def test_factory_returns_the_port(taxonomy):
    namer = server.taxonomy_category_namer()
    assert isinstance(namer, TaxonomyCategoryNamer)
    assert isinstance(namer, ICategoryNamer)


def test_factory_wires_the_real_taxonomy_functions(monkeypatch):
    monkeypatch.setattr(server, '_reporting_category_for_id', lambda cid: 'Wired')
    monkeypatch.setattr(
        server, '_resolve_reporting_category', lambda name: (11, 'cat-wired'))
    namer = server.taxonomy_category_namer()
    assert namer.name_for(1) == 'Wired'
    assert namer.id_for('anything') == 11


def test_factory_binds_late_so_a_cached_namer_still_sees_a_patch(monkeypatch):
    """The regression guard for the extraction.

    _get_expense_edit_repository caches its namer for the process lifetime, so
    a namer built BEFORE a test patches the taxonomy must still route through
    the patch. Passing the function objects into the constructor instead of
    lambdas breaks exactly this and nothing else in the file.
    """
    namer = server.taxonomy_category_namer()          # built first...
    monkeypatch.setattr(                              # ...patched after.
        server, '_reporting_category_for_id', lambda cid: 'Patched Late')
    monkeypatch.setattr(
        server, '_resolve_reporting_category', lambda name: (99, 'cat-late'))
    assert namer.name_for(1) == 'Patched Late'
    assert namer.id_for('anything') == 99


def test_factory_hands_back_an_independent_instance():
    assert server.taxonomy_category_namer() is not server.taxonomy_category_namer()


def test_factory_does_not_touch_the_database(monkeypatch):
    """Construction is wiring only; a namer is built on request paths where a
    connection may not exist yet."""
    def no_connections():
        raise AssertionError('taxonomy_category_namer opened a connection')

    monkeypatch.setattr(server, '_rol_get_connection', no_connections)
    server.taxonomy_category_namer()


def test_server_no_longer_defines_the_class_itself():
    """It is re-exported from finance.category_naming, not redeclared here --
    two copies of this adapter is the drift this extraction removes."""
    assert server.TaxonomyCategoryNamer.__module__ == 'finance.category_naming'


def test_edit_stored_expense_uses_the_factory_by_default(monkeypatch):
    """The default-argument path is the one production takes."""
    monkeypatch.setattr(
        server, '_resolve_reporting_category',
        lambda name: (77, 'cat-food') if name == 'Food' else (None, None))

    class Repo:
        def __init__(self):
            self.applied = []

        def apply_edit(self, edit):
            self.applied.append(edit)
            raise server.ExpenseNotFound('stop here, the id is what matters')

    repo = Repo()
    result = server.edit_stored_expense(
        {'expense_id': 5, 'merchant_name': 'Kroger',
         'transaction_date': '2026-08-15', 'total_amount': 1.0,
         'category_name': 'Food'},
        repository=repo)

    assert repo.applied and repo.applied[0].category_id == 77
    assert result['ok'] is False


def test_edit_stored_expense_reports_an_unknown_category_as_a_message(monkeypatch):
    """A bad pick is the operator's to fix, so it must not become a 500."""
    monkeypatch.setattr(
        server, '_resolve_reporting_category', lambda name: (None, None))

    class Repo:
        def apply_edit(self, edit):
            raise AssertionError('must not reach the repository')

    result = server.edit_stored_expense(
        {'expense_id': 5, 'merchant_name': 'Kroger',
         'transaction_date': '2026-08-15', 'total_amount': 1.0,
         'category_name': 'Nope'},
        repository=Repo())

    assert result['ok'] is False
    assert 'category' in result['error'].lower()


def test_edit_stored_expense_honours_an_injected_namer():
    """The seam the port exists for: a caller supplying its own namer."""

    class FixedNamer(ICategoryNamer):
        def name_for(self, category_id):
            return 'ignored'

        def id_for(self, category_name):
            return 4242

    class Repo:
        def __init__(self):
            self.applied = []

        def apply_edit(self, edit):
            self.applied.append(edit)
            raise server.ExpenseNotFound('stop here')

    repo = Repo()
    server.edit_stored_expense(
        {'expense_id': 5, 'merchant_name': 'Kroger',
         'transaction_date': '2026-08-15', 'total_amount': 1.0,
         'category_name': 'whatever'},
        repository=repo, namer=FixedNamer())

    assert repo.applied[0].category_id == 4242
