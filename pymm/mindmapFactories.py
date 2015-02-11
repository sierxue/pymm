import xml.etree.ElementTree as ET
from .mindmapElements import *
import warnings
from copy import deepcopy

#terminology  ... mme, mmElem, mmElement == MindMap element
            #.... ete, etElem, etElement == ElementTree element
            # element == could be either one. Sometimes it must conform to either one, other times it doesn't yet
                       # conform to a specific element

class BaseElementFactory(object):

    elementType = BaseElement
    childOrder = [BaseElement.tag, ArrowLink.tag, Cloud.tag, Edge.tag, Properties.tag, MapStyles.tag, Icon.tag,
                  AttributeLayout.tag, Attribute.tag, Hook.tag, Font.tag, StyleNode.tag, RichContent.tag, Node.tag]
                  # order in which children will be written to file
    lastChildOrder = []  # order of nth to last for children. First node listed will be last child.
    otherElementTypes = []  # if same tag can be used for different Elements, list them here, in a tuple with a
                         # distinguishing attribute name and its expected value: (element, attribName, attribValue)
    # xml etree appears to correctly convert html-safe to ascii: &lt; = <

    def __init__(self):
        self.childOrder = list(self.childOrder) + []  # make list instance so we don't modify class variable
        self.lastChildOrder = list(self.lastChildOrder) + []
        self.otherElementTypes = list(self.otherElementTypes) + []
        self.noFactoryWarnings = set()  # collect tags that didn't have factories and use it to send out ONE warning

    def display_any_warnings(self):
        if self.noFactoryWarnings:
            warnings.warn('elements ' + str(self.noFactoryWarnings) + ' do not have conversion factories. ' +
                           'Elements will import and export correctly, but warnings about specs will follow',
                           RuntimeWarning, stacklevel=2)
        self.noFactoryWarnings = set()  # reset warnings so we won't display the same ones

    def compute_element_type(self, etElement):
        etype = self.elementType  # default
        otherChoices = []
        for otherType, key, value in self.otherElementTypes:
            if key in etElement.attrib and etElement.attrib[key] == value:
                otherChoices.append(otherType)
        if len(otherChoices) > 1:
            warnings.warn(etElement.tag + ' has 2+ possible elements with which to convert with these attribs: ' +
                          str(etElement.attrib), RuntimeWarning, stacklevel=2)
        for possibleElementType in otherChoices:
            etype = possibleElementType  # choose last of choices, then
        return etype

    def convert_from_etree_element(self, etElement, parent):
        '''converts an xml etree etElement to a mmElem
        :param parent:
        If you return None, this etElement and all its children will be dropped from tree.
        '''
        etype = self.compute_element_type(etElement)  # choose between self.elementType and otherElementTypes
        mmElem = etype()  # could be anything: Map, Node, etc.
        attribs = self.convert_attribs(mmElem, etElement.attrib)
        mmElem = etype(attribs)  # yep, we initialize it a second time, but this time with attribs
        mmElem[:] = etElement[:]  # append all unconverted children to this mmElem!
        if not mmElem.tag == etElement.tag:
            self.noFactoryWarnings.add(etElement.tag)
            mmElem.tag = etElement.tag
        return mmElem

    def additional_conversion(self, mmElement, parent):  # should be called full tree conversion
        # If you return None, this element and all its children will be dropped from tree.
        return mmElement  # override by an inheriting class to perform addtional conversion before returning mmElement

    def revert_to_etree_element(self, mmElement, parent):
        # If you return None, this element and all its children will be dropped from tree.
        if isinstance(mmElement, ET.Element):  # we expected a pymm element, not an Etree Element
            warnings.warn('program is reverting an ET Element! ' + str(mmElement) + ' which means that it will lose text' +
            ' and tail properties. If you wish to preserve those, consider attaching ET Element as child of an' +
            ' Element in the "additional_reversion" function instead. This message indicates that the Element was ' +
            'added during the "revert_to_etree_element" function call. See RichContentFactory for an example.',
            RuntimeWarning, stacklevel=2)
        attribs = self.revert_attribs(mmElement)
        self.sort_element_children(mmElement)
        etElem = ET.Element(mmElement.tag, attribs)  # fyi: impossible to write attribs in specific order.
        etElem[:] = mmElement[:]
        etElem.text = mmElement._text
        etElem.tail = mmElement._tail
        return etElem

    def additional_reversion(self, etElement, parent):  # call after full tree reversion
        # If you return None, this etElement and all its children will be dropped from tree.
        if len(etElement) > 0 and not etElement.text:
            etElement.text = '\n'  # set spacing for written file layout, (but only if it has children!)
        if not etElement.tail:  # if tail is blank; we'll fill it in!
            etElement.tail = '\n'
        return etElement

    def sort_element_children(self, element):  # for reverting to etree element. Organizes children for file readability
        for tag in self.childOrder:
            children = element.findall(tag)
            for e in children:
                element.remove(e)
                element.append(e)
        for tag in reversed(self.lastChildOrder):  # nodes you want to show last
            children = element.findall(tag)
            for e in children:
                element.remove(e)
                element.append(e)

    def convert_attribs(self, mmElement, attribs):
        '''
        :param element - attribs from which to be converted:
        :param mmElement - mmElement to which to apply elements:
        :return mmElement:
        transfers all attributes from element to mmElement, converting where necessary.
        '''
        convertedAttribs = {}
        for key, value in attribs.items():  # converting from et element: assume all keys and values are strings
            try:
                if key in mmElement.specs:
                    vtype = mmElement.specs[key]
                    if isinstance(vtype, list):  # a list for multiple values (always strings)
                        vlist = vtype
                        if value not in vlist:
                            raise ValueError  # do nothing but warn. Do not change value
                    elif vtype == bool:  # boolean logic
                        truefalse = {'true': True,'false': False}
                        if value.lower() in truefalse:
                            value = truefalse[value.lower()]
                        else:
                            raise ValueError
                    else:
                        value = vtype(value)  # float or integer
                elif mmElement.specs:  # if we do have specs but didn't find our key in them, THEN give warning
                    raise ValueError
            except ValueError:
                warnings.warn('Attrib ' + key + '=' + value + ' not valid <' + mmElement.tag + '> specs', SyntaxWarning,
                              stacklevel=2)
            finally:
                convertedAttribs[key] = value
        return convertedAttribs

    def revert_attribs(self, mmElement):
        '''
        :param mmElement - attribs from which to be converted:
        :param element - element to which to apply attribs:
        :return element:
        transfers all attributes from mmElement to element, converting where necessary. If value conversion fails, simply
        convert value to string
        '''
        attribs = {key: value for key, value in mmElement.items() if value is not None}  # drop all None-valued attribs
        revertedAttribs = {}
        for key, value in attribs.items():
            if key in mmElement.specs:  # convert values, defaulting to str(value) if necessary
                vtype = mmElement.specs[key]
                if isinstance(vtype, list):  # a list for multiple values (always strings)
                    pass
                elif vtype == bool:  # boolean logic
                    value = str(value).lower()  # get 'false' or 'true' strings
                else:
                    value = str(vtype(value))  # float or integer
            key, value = str(key), str(value)
            revertedAttribs[key] = value
        return revertedAttribs


class NodeFactory(BaseElementFactory):
    elementType = Node
    childOrder = [BaseElement.tag, ArrowLink.tag, Cloud.tag, Edge.tag, Font.tag, Hook.tag, Properties.tag,
                  RichContent.tag, Icon.tag, Node.tag, AttributeLayout.tag, Attribute.tag]

    def additional_conversion(self, mmNode, parent):
        super(NodeFactory, self).additional_conversion(mmNode, parent)
        mmNode = self.convert_node_text(mmNode)
        return mmNode

    def revert_to_etree_element(self, mmNode, parent):
        mmNode = self.revert_node_text(mmNode)
        return super(NodeFactory, self).revert_to_etree_element(mmNode, parent)

    def revert_node_text(self, mmNode):
        ntext = NodeText()  # developer / user NEVER needs to create his own RichContent for mmNode html
        ntext.html = mmNode['TEXT']
        if ntext.is_html():
            mmNode.append(ntext)
            del mmNode['TEXT']  # using richcontent, do not leave attribute 'TEXT' for mmNode
        return mmNode

    def convert_node_text(self, mmNode):
        richElements = mmNode.findall('richcontent')
        while richElements:
            richElem = richElements.pop(0)
            if isinstance(richElem, NodeText):
                mmNode['TEXT'] = richElem.html
                mmNode.remove(richElem)  # this NodeText is no longer needed
        return mmNode

class MapFactory(BaseElementFactory):
    elementType = Map

    def additional_reversion(self, etMap, parent):
        etMap = super(MapFactory, self).additional_reversion(etMap, parent)
        comment = ET.Comment('To view this file, download free mind mapping software Freeplane from ' +
                   'http://freeplane.sourceforge.net')
        comment.tail = '\n'
        etMap[:] = [comment] + etMap[:]
        return etMap

class CloudFactory(BaseElementFactory):
    elementType = Cloud

class HookFactory(BaseElementFactory):
    elementType = Hook
    otherElementTypes = [(EmbeddedImage, 'NAME', 'ExternalObject'),(MapConfig, 'NAME', 'MapStyle'),
                         (Equation, 'NAME', 'plugins/latex/LatexNodeHook.properties'),
                         (AutomaticEdgeColor, 'NAME', 'AutomaticEdgeColor')]

class MapStylesFactory(BaseElementFactory):
    elementType = MapStyles

class StyleNodeFactory(BaseElementFactory):
    elementType = StyleNode

class FontFactory(BaseElementFactory):
    elementType = Font

class IconFactory(BaseElementFactory):
    elementType = Icon

class EdgeFactory(BaseElementFactory):
    elementType = Edge

class AttributeFactory(BaseElementFactory):
    elementType = Attribute

class PropertiesFactory(BaseElementFactory):
    elementType = Properties

class AttributeRegistryFactory(BaseElementFactory):
    elementType = AttributeRegistry

class RichContentFactory(BaseElementFactory):
    elementType = RichContent
    otherElementTypes = [(NodeText, 'TYPE', 'NODE'), (NodeNote, 'TYPE', 'NOTE'), (NodeDetails, 'TYPE', 'DETAILS')]

    def convert_from_etree_element(self, etRichC, parent):
        mmRichC = super(RichContentFactory, self).convert_from_etree_element(etRichC, parent)
        html = ''                        # this makes a critical assumption that there'll be 1 child. If not, upon
        for htmlElement in mmRichC:  # reversion, ET may complain about "ParseError: junk after document etRichC...
            html += ET.tostring(htmlElement)
        mmRichC.html = html
        mmRichC[:] = []  # remove html children to prevent their conversion.
        return mmRichC

    def revert_to_etree_element(self, mmRichC, parent):
        html = mmRichC.html
        element = super(RichContentFactory, self).revert_to_etree_element(mmRichC, parent)
        element.text = html  # temporarily store html string in element.text  (will convert in additional_reversion)
        return element

    def additional_reversion(self, etRichC, parent):
        html = etRichC.text
        etRichC.text = '\n'
        super(RichContentFactory, self).additional_reversion(etRichC, parent)  # just sets tail...
        etRichC.append(ET.fromstring(html))  # this etRichC will have additional_reversion() called on it. It Should
        return etRichC                       # have no effect, however.


class MindMapFactory(object):
    # pass this factory a node to convert
    # and it will convert by choosing which factory to use in converting a given node
    # it is also tasked with non-recursively converting all nodes contained
    # within the first converted node.
    # you can add_factory(factory) if you have created a new node type / new factory to handle different features here

    def __init__(self, **kwargs):
        factories = [BaseElementFactory, NodeFactory, MapFactory, CloudFactory,
                     HookFactory, MapStylesFactory, StyleNodeFactory, FontFactory, IconFactory,
                     EdgeFactory, AttributeFactory, PropertiesFactory, RichContentFactory,
                     AttributeRegistryFactory]
        fff = [factory() for factory in factories]  # get an initialized instance of all factories
        self.tag2factory = {}
        for f in fff:            # get a dictionary that
            self.add_factory(f)  # matches an elements tag to the factory which can handle that element
        self.defaultFactory = BaseElementFactory()

    def add_factory(self, factory):
        if not isinstance(factory, object):  # if we are passed a non-initialized factory, create factory instance
            factory = factory()
        element = factory.elementType()
        self.tag2factory[element.tag] = factory

    def _special_vert_full_tree(self, element, action1, action2):
        # element can be pymm element or etree element
        # e = from (the node / element being converted)
        # convert or revert the element!
        first = action1(element, None)
        hasUnchangedChildren = [first]
        while hasUnchangedChildren:
            element = hasUnchangedChildren.pop(0)
            unchanged = [(child, element) for child in element[:]] # combine child w/ parent into tuple
            children = []
            while unchanged:
                unchangedChild, parent = unchanged.pop(0)  # pop from first index to preserve child order
                child = action1(unchangedChild, parent)
                if child is None:
                    continue  # removes element from tree being built by not adding it to children(s) list
                children.append(child)
                hasUnchangedChildren.append(child)
            element[:] = children
        notFullyChanged = [(first, None)]  # child = first. Parent = None
        while notFullyChanged:
            element, parent = notFullyChanged.pop(0)
            elem = action2(element, parent)
            if elem is None:
                if element in parent[:]:    # if you return None during conversion / reversion, this will ensure it is
                    parent.remove(element)  # fully removed from the tree by removing its reference from the parent
                continue                    # and not allowing its children to be added.
            parentsAndChildren = [(child, elem) for child in elem[:]]  # child w/ parent
            notFullyChanged.extend(parentsAndChildren)
        return first

    def convert_etree_element_and_tree(self, etElement):
        etElement = deepcopy(etElement)
        action1 = self.convert_etree_element
        action2 = self.additional_conversion
        node = self._special_vert_full_tree(etElement, action1, action2)
        self.defaultFactory.display_any_warnings()  # get this out so the developer is warned.
        return node

    def convert_etree_element(self, etElement, parent):
        ff = self.get_conversion_factory_for(etElement)
        node = ff.convert_from_etree_element(etElement, parent)
        return node

    def additional_conversion(self, mmElement, parent):
        ff = self.get_conversion_factory_for(mmElement)
        return ff.additional_conversion(mmElement, parent)

    def get_conversion_factory_for(self, element):  # intended for etElement or mmElement
        tag = element.tag
        if tag and tag in self.tag2factory:
            return self.tag2factory[tag]
        return self.defaultFactory

    def revert_mm_element_and_tree(self, mmElement):
        mmElement = deepcopy(mmElement)
        action1 = self.revert_mm_element
        action2 = self.additional_reversion
        return self._special_vert_full_tree(mmElement, action1, action2)

    def revert_mm_element(self, mmElement, parent):
        ff = self.get_conversion_factory_for(mmElement)
        return ff.revert_to_etree_element(mmElement, parent)

    def additional_reversion(self, etElement, parent):
        ff = self.get_conversion_factory_for(etElement)
        return ff.additional_reversion(etElement, parent)