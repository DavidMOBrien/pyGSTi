
from ..testutils import BaseTestCase

# Imported by other modules that test formatters (reduces duplicate code)
class FormatterBaseTestCase(BaseTestCase):
    def setUp(self):
        super(FormatterBaseTestCase, self).setUp()

        self.arbitraryNum = 1.819743 # Six digits after decimal
        self.roundedNum   = 1.82     # Two digits after decimal

        latexString = '\\begin{tabular}[l]{|c|}\n\hline\n%s \\\\ \hline\n\end{tabular}\n'
        htmlString  = '<table><thead><tr><th> %s </th></tr></thead><tbody></tbody></table>'

        self.precise   = {
            'html'  : htmlString  % self.arbitraryNum,
            'latex' : latexString % self.arbitraryNum}

        self.imprecise = {
            'html'  : htmlString  % self.roundedNum,
            'latex' : latexString % self.roundedNum}

    def render_pair(self, heading, formatter, formattype='latex', **kwargs):
        headings   = [heading]
        formatters = [formatter]
        table      = ReportTable(headings, formatters)
        return table.render(formattype, **kwargs)[formattype]

import pygsti.report.formatters as formatter
from pygsti.report.table import ReportTable

class GenericFormatterTests(FormatterBaseTestCase):
    def setUp(self):
        super(GenericFormatterTests, self).setUp()

    def test_none_formatter(self):
        formatter.FormatSet.formatDict['BadFormat'] = {
            'latex' : lambda l, s : None,
            'html'  : lambda l, s : None,
            'text'  : lambda l, s : None,
            'ppt'   : lambda l, s : None,
            }

        with self.assertRaises(ValueError):
            self.render_pair('some_heading', 'BadFormat')

    def test_unformatted_none(self):
        with self.assertRaises(ValueError):
            self.render_pair(None, None)

    def test_unformatted(self):
        self.render_pair('some heading', None)

    def test_string_return(self):
        self.assertEqual(self.render_pair('remainder', 'Effect', 'html'),
                         '<table><thead><tr><th> E<sub>C</sub> </th></tr></thead><tbody></tbody></table>')

    def test_string_replace(self):
        self.assertEqual(self.render_pair('rho0', 'Rho', 'html'),
                         '<table><thead><tr><th> &rho;<sub>0</sub> </th></tr></thead><tbody></tbody></table>')

    def test_no_format(self):
        self.assertEqual(formatter.no_format('x'), 'x')

    def test_conversion_formatters(self):
        self.assertEqual(formatter._fmtCnv_html('|<STAR>'), ' &#9733;')
        self.assertEqual(formatter._fmtCnv_latex('%% # half-width 1/2 Diamond Check <STAR>'),
               '$\%\% \# $\\nicefrac{1}{2}$-width $\\nicefrac{1}{2}$ $\Diamond$ \checkmark \\bigstar$')
        self.assertEqual(formatter._fmtCnv_latex('x|y'), '\\begin{tabular}{c}x\\\\y\end{tabular}')

if __name__ == '__main__':
    import unittest
    unittest.main(verbosity=1)
