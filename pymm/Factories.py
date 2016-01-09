"""Factories are responsible for decoding xml.etree Elements into pymm
Elements and encoding pymm Elements back to xml.etree Elements. Factories are
where to specify how the encoding and decoding of an element is handled. Attrib
encoding/decoding is handled here as well
"""
import xml.etree.ElementTree as ET
import warnings
import copy
import re
import types
from . import Elements

#terminology  ... mme, mmElem, mmElement == MindMap element
#.... ete, etElem, etElement == ElementTree element
# element == could be either one. Sometimes it must conform to either one,
# other times it doesn't yet
# conform to a specific element

# an example factory that shows which methods you'll need to override when
# inheriting from BaseElementFactory
class ExampleElementFactory:  
    def encode_to_etree_element(self, mmElement, parent=None):
        # does all the heavy lifting.
        etElement = super().encode_to_etree_element(mmElement, parent)
        raise NotImplementedError(
                'DO NOT use ExampleElementFactory. Inherit '
                + 'from BaseElementFactory Instead!'
        )
        return etElement

    def decode_from_etree_element(self, etElement, parent=None):
        mmElem = super().decode_from_etree_element(etElement, parent)
        raise NotImplementedError(
                'DO NOT use ExampleElementFactory. Inherit from '
                + 'BaseElementFactory Instead!'
        )
        return mmElem

# a super-simple encoder to use in encoding your custom nodes
# into another format.
class SimpleEncoder:

    def write(self, filename, node_tree):
        with open(filename, 'w') as self.file:
            # SimpleEncoder only works with nodes, since it's expected to be
            # the only usable part of the mindmap.
            self.encode_node_tree_depth_first(node_tree)

    def encode_node_tree_depth_first(self, node):
        self.encode_node(node)
        for child in node.nodes:
            self.encode_node_tree_depth_first(child)

# this is the only method you need to override.
    def encode_node(self, node):
        self.file.writeline(node.attrib['TEXT'])


def sanity_check(pymm_element):
    """checks for common errors in pymm element and issues warnings
    for out-of-spec attrib
    """
    unchecked = [pymm_element]
    while unchecked:
        elem = unchecked.pop(0)
        unchecked.extend(elem.children)
        attrib = elem.attrib
        for key, allowed_values in elem.spec.items():
            if key in attrib:
                attribute = attrib[key]
                for allowed in allowed_values:
                    if attribute == allowed or isinstance(attribute, allowed):
                        break
                    # allow attribute if spec contains a function
                    if isinstance(allowed, types.BuiltinMethodType) or \
                       isinstance(allowed, types.LambdaType) or \
                       isinstance(allowed, types.MethodType) or \
                       isinstance(allowed, types.FunctionType) or \
                       isinstance(allowed, types.BuiltinFunctionType):
                        break
                else:
                    warnings.warn(
                        'out-of-spec attribute "' + str(attribute) +
                        ' in element: ' + str(elem.tag)
                    )


class BaseElementFactory:
    ''' decode between ElementTree elements and pymm elements.
    Conversion from ElementTree element to pymm elements is done by
    passing the etElement to decode_from_et_element() After decoding
    the full tree's worth of elements, re-iterate through the tree
    (starting at top-level) and pass that element into this factory's
    finish_decode(). For each decode / encode function,
    decode the full xml tree before using the finish_ function.
    Factory does not keep children. In decoding full xml-tree, you
    will have to add the children how you see fit. Generally, it is best
    to add the children after initial decode / encode and then
    immediately decode / encode those children. This pattern avoids
    recursion limits in python.
    '''
    element = Elements.BaseElement
    # order in which children will be written to file
    child_order = [
        Elements.BaseElement, Elements.ArrowLink, Elements.Cloud,
        Elements.Edge, Elements.Properties, Elements.MapStyles, Elements.Icon,
        Elements.AttributeLayout, Elements.Attribute, Elements.Hook,
        Elements.Font, Elements.StyleNode, Elements.RichContent, Elements.Node
    ]
    # order of nth to last for children. First node listed will be last child.
    reverse_child_order = []
    # if same tag can be used for different Elements, list them here, in a
    # tuple with a dictionary of distinguishing attribute name and its
    # expected value: (element, {attribName: attribValue})
    typeVariants = []
    # xml etree appears to correctly decode html-safe to ascii: &lt; = <

    def __init__(self):
        # make list instance so we don't modify class variable
        self.child_order = self.child_order.copy()
        self.reverse_child_order = self.reverse_child_order.copy()
        self.typeVariants = self.typeVariants.copy()
        # collect tags that didn't have factories and use it to send out ONE
        # warning
        self.noFactoryWarnings = set()

    def display_any_warnings(self):
        '''Display warnings for elements found without a specific factory.
        Call once after full decode / encode
        '''
        if self.noFactoryWarnings:
            warnings.warn(
                'elements ' + str(self.noFactoryWarnings) +  ' do not have '
                + 'decode factories. Elements will import and export '
                + 'correctly, but warnings about spec will follow',
                RuntimeWarning, stacklevel=2
            )
        # reset warnings so we won't display the same ones
        self.noFactoryWarnings = set()

    def compute_element_type(self, etElement):
        '''Choose amongst several pymm elements for etree element with
        same tag using attribute properties. Used in special cases when
        user wants to sub-categorize elements with the same tag. For
        example, RichContent has several different types: NODE, NOTE,
        and DETAILS. Specify which type of element to create by adding
        attribute distinguishers to factory.typeVariants. The same
        factory will be used, however.
        '''
        otherChoices = []
        for otherType, attribs in self.typeVariants:
            for key, regex in attribs.items():
                if key not in etElement.attrib:
                    break
                attrib = etElement.attrib[key]
                if not re.fullmatch(regex, attrib):
                    break  # we only accept if regex fully matches attrib
            else:  # if all attribs match, this triggers
                otherChoices.append(otherType)
        if len(otherChoices) > 1:
            warnings.warn(
                etElement.tag + ' has 2+ possible elements with which to '
                + 'decode with these attribs: ' + str(etElement.attrib),
                RuntimeWarning, stacklevel=2
            )
        if otherChoices:
            return otherChoices[-1]  # choose last of choices
        return self.element  # default if no other choices found

    def decode_from_etree_element(self, etElement, parent=None):
        '''decodes an etree etElement to a pymm element

        :param parent:
        :returns mmElement or None
        If you return None, this etElement and all its children will be
        dropped from tree.
        '''
        # choose between self.element and typeVariants
        elemClass = self.compute_element_type(etElement)
        attrib = self.decode_attribs(elemClass, etElement.attrib)
        mmElem = elemClass(**attrib)  # yep, we initialize it a second time,
        mmElem.children = [c for c in etElement[:]]
        if not mmElem.tag == etElement.tag:
            self.noFactoryWarnings.add(etElement.tag)
            mmElem.tag = etElement.tag
        return mmElem

    # should be called full tree decode
    def finish_decode(self, mmElement, parent=None):
        ''' Finishes decode of mindmap element. Call only after
        decode_from_etree_element() has decoded tree

        :return mindmap Element or None
        if return None, it is expected that this element and all its
        children will be dropped from tree
        '''
        return mmElement

    def encode_to_etree_element(self, mmElement, parent=None):
        # If you return None, this element and all its children will be
        # dropped from tree.
        if isinstance(mmElement, ET.Element):
            # we expected a pymm element, not an Etree Element
            warnings.warn(
                'program is encoding an ET Element! ' + str(mmElement)
                + ' which means that it will lose text and tail properties. '
                + 'If you wish to preserve those, consider attaching ET '
                + 'Element as child of an Element in the '
                + '"additional_encode" function instead. This message '
                + 'indicates that the Element was added during the '
                + '"encode_to_etree_element" function call. See '
                + 'RichContentFactory for an example.',
                RuntimeWarning, stacklevel=2
            )
        attribs = self.encode_attribs(mmElement)
        self.sort_element_children(mmElement)
        # fyi: it's impossible to write attribs in specific order.
        etElem = ET.Element(mmElement.tag, attribs)
        etElem[:] = mmElement.children
        etElem.text = mmElement._text
        etElem.tail = mmElement._tail
        return etElem

    def finish_encode(self, etElement, parent=None):
        """Call after full tree encode. If you return None, this
        etElement and all its children will be dropped from tree.
        """
        # prettify file layout with newlines for readability
        if len(etElement) > 0 and not etElement.text:
            etElement.text = '\n'
        if not etElement.tail:
            etElement.tail = '\n'
        return etElement

    def sort_element_children(self, element):
        """For encoding to etree element. Organize children as written to file
        for file readability (by placing nodes closer to top of chilren)
        """
        for child_element in self.child_order:
            tag = child_element.tag
            children = element.findall(tag_regex=tag)
            for e in children:
                element.children.remove(e)
                element.children.append(e)
        # nodes you want to show last
        for child_element in reversed(self.reverse_child_order):
            tag = child_element.tag
            children = element.findall(tag_regex=tag)
            for e in children:
                element.children.remove(e)
                element.childern.append(e)

    def decode_attribs(self, mmElement, attribs):
        '''Using mmElement (class or instance) as guide, decode
        attribs (from etree element) to match the spec in mmElement.
        Warn (but still allow it) if attribute key/value pair is not
        valid
        '''
        decoded_attribs = {}
        # decoding from et element: assume all keys and values are strings
        for key, value in attribs.items():
            try:
                if key not in mmElement.spec and mmElement.spec:
                    raise ValueError(
                        '"' + str(key) + '" was not found in spec'
                    )
                entries = mmElement.spec[key]
                value = self.decode_attrib_value_using_spec_entries(
                            key, value, entries
                        )
            except ValueError:
                warnings.warn(
                    'Attrib ' + key + '=' + value + ' not valid <'
                    + mmElement.tag + '> spec', SyntaxWarning, stacklevel=2
                )
            finally:
                # add attribute regardless of errors
                decoded_attribs[key] = value
        return decoded_attribs

    def decode_attrib_value_using_spec_entries(self, key, value, entries):
        # first verify that entries is a list
        if not isinstance(entries, list):
            raise ValueError('spec contained a non-list spec-value')
        for entry in entries:
            if isinstance(entry, type):  # bool, str, int, etc...
                valueType = entry
                # special handling for bool since bool('false') == True.
                # Therefore we check if value is a false
                if issubclass(valueType, bool):
                    false_strings = [
                        'false', 'False', 'FALSE', b'false', b'False',
                        b'FALSE'
                    ]
                    if value in false_strings:
                        value = False
                        break
                value = valueType(value)  # decode value to new type
                break
            elif isinstance(entry, types.LambdaType) or \
                 isinstance(entry, types.BuiltinFunctionType) or \
                 isinstance(entry, types.BuiltinMethodType) or \
                 isinstance(entry, types.FunctionType) or \
                 isinstance(entry, types.MethodType):
                valuedecoder = entry
                value = valuedecoder(value)  # decode value using function
                break
            else:
                valueString = entry
                if valueString == value:
                    break
        else:
            value = str(value)
            warnings.warn(
                str(key) + ':' + value + '" not matched or converted by spec'
            )
        return value

    def encode_attribs(self, mmElement):
        '''
        using mmElements' spec, encodes attribs to string instances,
        validating that value are proper type. If a specific attribs'
        value is None, attrib will not be included. if attrib is not
        in spec, attrib will not be included

        :param mmElement - pymm element containing attribs to be
        encoded
        '''
        # drop all None-valued attribs
        attribs = {
            key: value for key, value in mmElement.attrib.items() if \
            value is not None
        }
        encoded_attribs = {}
        for key, value in attribs.items():
            if key not in mmElement.spec:
                continue  # WARNING: skip adding attrib that isn't in spec???
            entries = mmElement.spec[key]
            value = self.decode_attrib_value_using_spec_entries(
                key, value, entries
            )
            key, value = str(key), str(value)
            encoded_attribs[key] = value
        return encoded_attribs


class NodeFactory(BaseElementFactory):
    element = Elements.Node
    child_order = [
        Elements.BaseElement, Elements.ArrowLink, Elements.Cloud,
        Elements.Edge, Elements.Font, Elements.Hook, Elements.Properties,
        Elements.RichContent, Elements.Icon, Elements.Node,
        Elements.AttributeLayout, Elements.Attribute
    ]

    def decode_attribs(self, mmElement, attrib):
        """Replace undesired parts of attrib with desired parts.
        specifically: look for occasional LOCALIZED_TEXT attrib which
        is supposed to be TEXT
        """
        swapout = [('TEXT', 'LOCALIZED_TEXT')]
        for desired, undesired in swapout:
            if desired not in attrib and undesired in attrib:
                attrib[desired] = attrib[undesired]
                del attrib[undesired]
        return super().decode_attribs(mmElement, attrib)

    def finish_decode(self, mmElement, parent=None):
        super().finish_decode(mmElement, parent)
        self.decode_node_text(mmElement)
        return mmElement

    def encode_to_etree_element(self, mmElement, parent=None):
        self.encode_node_text(mmElement)
        return super().encode_to_etree_element(mmElement, parent)

    def encode_node_text(self, mmNode):
        '''If node text is html, creates html child and appends to
        node's children
        '''
        # developer / user NEVER needs to create his own RichContent for
        # mmNode html
        ntext = Elements.NodeText()
        ntext.html = mmNode.attrib['TEXT']
        if ntext.is_html():
            mmNode.children.append(ntext)
            # using richcontent, do not leave attribute 'TEXT' for mmNode
            del mmNode.attrib['TEXT']

    def decode_node_text(self, mmNode):
        '''If node has html text, set to TEXT attribute to html object'''
        richElements = mmNode.findall(tag_regex=r'richcontent')
        while richElements:
            richElem = richElements.pop(0)
            if isinstance(richElem, Elements.NodeText):
                mmNode.attrib['TEXT'] = richElem.html
                # this NodeText is no longer needed
                mmNode.children.remove(richElem)


class MapFactory(BaseElementFactory):
    element = Elements.Map

    def finish_encode(self, etElement, parent=None):
        etMap = super().finish_encode(etElement, parent)
        comment = ET.Comment(
            'To view this file, download free mind mapping software '
            + 'Freeplane from http://freeplane.sourceforge.net'
        )
        comment.tail = '\n'
        etMap[:] = [comment] + etMap[:]
        return etMap

class CloudFactory(BaseElementFactory):
    element = Elements.Cloud

class HookFactory(BaseElementFactory):
    element = Elements.Hook
    typeVariants = [
        (Elements.EmbeddedImage, {'NAME': r'ExternalObject'}),
        (Elements.MapConfig, {'NAME': r'MapStyle'}),
        (Elements.Equation, {'NAME': r'plugins/latex/LatexNodeHook\.properties'}),
        (Elements.AutomaticEdgeColor, {'NAME': r'AutomaticEdgeColor'})
    ]

class MapStylesFactory(BaseElementFactory):
    element = Elements.MapStyles

class StyleNodeFactory(BaseElementFactory):
    element = Elements.StyleNode

class FontFactory(BaseElementFactory):
    element = Elements.Font

class IconFactory(BaseElementFactory):
    element = Elements.Icon

class EdgeFactory(BaseElementFactory):
    element = Elements.Edge

class AttributeFactory(BaseElementFactory):
    element = Elements.Attribute

class PropertiesFactory(BaseElementFactory):
    element = Elements.Properties

class AttributeRegistryFactory(BaseElementFactory):
    element = Elements.AttributeRegistry

class RichContentFactory(BaseElementFactory):
    element = Elements.RichContent
    typeVariants = [
        (Elements.NodeText, {'TYPE': r'NODE'}),
        (Elements.NodeNote, {'TYPE': r'NOTE'}),
        (Elements.NodeDetails, {'TYPE': r'DETAILS'})
    ]

    def decode_from_etree_element(self, etElement, parent=None):
        mmRichC = super().decode_from_etree_element(etElement, parent)
# this makes a critical assumption that there'll be 1 child. If not, upon
# encode, ET may complain about "ParseError: junk after document etRichC..
        html = ''
        for htmlElement in mmRichC.children:
            htmlString = ET.tostring(htmlElement)
            if not isinstance(htmlString, str):
                # I have once got back <class 'bytes'> when the string was a
                # binary string. weird...
                htmlString = htmlString.decode('ascii')
            html += htmlString
        mmRichC.html = html
  # remove html children to prevent their decode.
        mmRichC.children.clear()
        return mmRichC

    def encode_to_etree_element(self, mmElement, parent=None):
        html = mmElement.html
        element = super().encode_to_etree_element(mmElement, parent)
# temporarily store html string in element.text  (will decode in
# additional_encode)
        element.text = html
        return element

    def finish_encode(self, etElement, parent=None):
        html = etElement.text
        etElement.text = '\n'
        etRichC = super().finish_encode(etElement, parent)  # sets tail
# this etRichC will have additional_encode() called on it. It Should
# have no effect, however
        etRichC.append(ET.fromstring(html))
        return etRichC


class MindMapConverter:
    """Pass this converter a node to decode and it will decode by
    choosing which factory to use in decoding a given node it is also
    tasked with non-recursively decoding all nodes contained within
    the first decoded node. You can add_factory(factory) if you have
    created a new node type / new factory to handle different features
    here
    """

    def __init__(self, **kwargs):
        factoryClasses = [
            BaseElementFactory, NodeFactory, MapFactory, CloudFactory,
            HookFactory, MapStylesFactory, StyleNodeFactory, FontFactory, 
            IconFactory, EdgeFactory, AttributeFactory, PropertiesFactory,
            RichContentFactory, AttributeRegistryFactory
        ]
# get an initialized instance of all factories
        fff = [factory() for factory in factoryClasses]
        self.tag2factory = {}
        # get a dictionary matches an elements tag to the factory which
        # can handle that element
        for f in fff:
            self.add_factory(f)
        self.defaultFactory = BaseElementFactory()

    def add_factory(self, factory):
        '''Add or Overwrite factory used for xml element. Specific to
        a tag specified by the factory's element

        :param factory: a pymm element factory
        '''
        # if we are passed a non-initialized factory, create factory instance
        if not isinstance(factory, object):
            factory = factory()
        element = factory.element()
        self.tag2factory[element.tag] = factory

    def _apply_decode_fxns_to_full_tree(self, element, fxn1, fxn2):
        firstPassRoot = self._apply_first_pass_fxn_to_full_tree(element, fxn1)
        return self._apply_second_pass_fxn_to_full_tree(firstPassRoot, fxn2)

    def _apply_first_pass_fxn_to_full_tree(self, element, fxn1):
        first = fxn1(element, None)
        hasUnchangedChildren = [first]
        while hasUnchangedChildren:
            element = hasUnchangedChildren.pop(0)
            if isinstance(element, Elements.BaseElement):
                # combine child w/ parent into tuple
                unchanged = [(child, element) for child in element.children]
            else:
                # xml.etree format
                unchanged = [(child, element) for child in element[:]]
            children = []
            while unchanged:
                # preserve child order by popping from front of list
                unchangedChild, parent = unchanged.pop(0)
                child = fxn1(unchangedChild, parent)
                if child is None:
                    # removes element from tree being built by not adding
                    # it to children(s) list
                    continue
                children.append(child)
                hasUnchangedChildren.append(child)
            if isinstance(element, Elements.BaseElement):
                element.children = children  # pymm format
            else:
                element[:] = children  # xml.etree format
        return first
    

    def _apply_second_pass_fxn_to_full_tree(self, element, fxn2):
        first = element
        notFullyChanged = [(first, None)]  # child = first. Parent = None
        while notFullyChanged:
            element, parent = notFullyChanged.pop(0)
            elem = fxn2(element, parent)
            if elem is None and parent is not None:
                # if you return None during decode / encode, this
                # will ensure it is fully removed from the tree by removing
                # its reference from the parent and not allowing its children
                # to be added
                self._remove_child_element(elem, parent)
                continue
            if isinstance(elem, Elements.BaseElement):
                children = elem.children  # pymm syntax
            else:
                children = list(elem)  # xml.etree.ElementTree syntax
            parentsAndChildren = [(child, elem) for child in children]
            notFullyChanged.extend(parentsAndChildren)
        return first

    def _remove_child_element(self, child, parent):
        if isinstance(parent, Elements.BaseElement):
            parent.children.remove(child)  # pymm format
        else:
            parent.remove(child)  # xml.etree format

    def decode_etree_element_and_tree(self, etElement):
        etElement = copy.deepcopy(etElement)
        action1 = self.decode_etree_element
        action2 = self.additional_decode
        node = self._apply_decode_fxns_to_full_tree(etElement, action1, action2)
        # finally, warn developer of any problems during decode
        self.defaultFactory.display_any_warnings()
        return node

    def decode_etree_element(self, etElement, parent):
        ff = self.get_decode_factory_for(etElement)
        node = ff.decode_from_etree_element(etElement, parent)
        return node

    def additional_decode(self, mmElement, parent):
        ff = self.get_decode_factory_for(mmElement)
        return ff.finish_decode(mmElement, parent)

    def get_decode_factory_for(self, element):
        '''Intended for etElement or mmElement'''
        tag = element.tag
        if tag and tag in self.tag2factory:
            return self.tag2factory[tag]
        return self.defaultFactory

    def encode_mm_element_and_tree(self, mmElement):
        mmElement = copy.deepcopy(mmElement)
        action1 = self.encode_mm_element
        action2 = self.additional_encode
        return self._apply_decode_fxns_to_full_tree(
                   mmElement, action1, action2
               )

    def encode_mm_element(self, mmElement, parent):
        ff = self.get_decode_factory_for(mmElement)
        return ff.encode_to_etree_element(mmElement, parent)

    def additional_encode(self, etElement, parent):
        ff = self.get_decode_factory_for(etElement)
        return ff.finish_encode(etElement, parent)
