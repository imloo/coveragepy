# test coverage.py
# Copyright 2004-2009, Ned Batchelder
# http://nedbatchelder.com/code/modules/coverage.html

# Change this 0 to 1 to get diagnostic output during testing.
showstdout = 0

import unittest
import imp, os, pprint, random, sys, tempfile
from cStringIO import StringIO

import path     # from http://www.jorendorff.com/articles/python/path/

import coverage

CovExc = coverage.CoverageException

from textwrap import dedent
    

coverage.use_cache(0)


class CoverageTest(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory.
        self.noise = str(random.random())[2:]
        self.temproot = path.path(tempfile.gettempdir()) / 'test_coverage' 
        self.tempdir = self.temproot / self.noise
        self.tempdir.makedirs()
        self.olddir = os.getcwd()
        os.chdir(self.tempdir)
        # Keep a counter to make every call to checkCoverage unique.
        self.n = 0

        # Capture stdout, so we can use print statements in the tests and not
        # pollute the test output.
        self.oldstdout = sys.stdout
        self.capturedstdout = StringIO()
        if not showstdout:
            sys.stdout = self.capturedstdout
        coverage.begin_recursive()
        
    def tearDown(self):
        coverage.end_recursive()
        sys.stdout = self.oldstdout
        # Get rid of the temporary directory.
        os.chdir(self.olddir)
        self.temproot.rmtree()

    def getStdout(self):
        return self.capturedstdout.getvalue()
    
    def makeFile(self, modname, text):
        """ Create a temp file with modname as the module name, and text as the
            contents.
        """
        text = dedent(text)
        
        # Create the python file.
        f = open(modname + '.py', 'w')
        f.write(text)
        f.close()

    def importModule(self, modname):
        """ Import the module named modname, and return the module object.
        """
        modfile = modname + '.py'
        f = open(modfile, 'r')
        
        for suff in imp.get_suffixes():
            if suff[0] == '.py':
                break
        try:
            mod = imp.load_module(modname, f, modfile, suff)
        finally:
            f.close()
        return mod

    def getModuleName(self):
        # We append self.n because otherwise two calls in one test will use the
        # same filename and whether the test works or not depends on the
        # timestamps in the .pyc file, so it becomes random whether the second
        # call will use the compiled version of the first call's code or not!
        modname = 'coverage_test_' + self.noise + str(self.n)
        self.n += 1
        return modname
    
    def checkCoverage(self, text, lines, missing="", excludes=[], report=""):
        self.checkEverything(text=text, lines=lines, missing=missing, excludes=excludes, report=report)
        
    def checkEverything(self, text=None, file=None, lines=None, missing=None, 
            excludes=[], report="", annfile=None):
        assert text or file
        assert not (text and file)
        
        # We write the code into a file so that we can import it.
        # coverage.py wants to deal with things as modules with file names.
        modname = self.getModuleName()
        
        if text:
            self.makeFile(modname, text)
        elif file:
            p = path.path(self.olddir) / file
            p.copyfile(modname + '.py')

        # Start up coverage.py
        coverage.erase()
        for exc in excludes:
            coverage.exclude(exc)
        coverage.start()

        # Import the python file, executing it.
        mod = self.importModule(modname)
        
        # Stop coverage.py
        coverage.stop()

        # Clean up our side effects
        del sys.modules[modname]

        # Get the analysis results, and check that they are right.
        _, clines, _, cmissing = coverage.analysis(mod)
        if lines is not None:
            if type(lines[0]) == type(1):
                self.assertEqual(clines, lines)
            else:
                for line_list in lines:
                    if clines == line_list:
                        break
                else:
                    self.fail("None of the lines choices matched %r" % clines)
        if missing is not None:
            if type(missing) == type(""):
                self.assertEqual(cmissing, missing)
            else:
                for missing_list in missing:
                    if cmissing == missing_list:
                        break
                else:
                    self.fail("None of the missing choices matched %r" % cmissing)

        if report:
            frep = StringIO()
            coverage.report(mod, file=frep)
            rep = " ".join(frep.getvalue().split("\n")[2].split()[1:])
            self.assertEqual(report, rep)

        if annfile:
            # Run annotate.
            coverage.annotate([modname+'.py'])
            expect = (path.path(self.olddir) / annfile).text()
            actual = path.path(modname + '.py,cover').text()
            # Write the actual results into a file for comparison.
            out = path.path(self.olddir) / (annfile + "_actual_%s%s" % (sys.version_info[:2]))
            # Check if the results are right
            if expect == actual:
                # They are right: delete the old test results if they are still
                # around.
                if out.exists():
                    out.remove()
            else:
                # The results are wrong: write them out so we can diff them to
                # see what happened.
                out.write_text(actual)
                self.fail("Annotation is incorrect: %s" % out)

    def assertRaisesMsg(self, excClass, msg, callableObj, *args, **kwargs):
        """ Just like unittest.TestCase.assertRaises,
            but checks that the message is right too.
        """
        try:
            callableObj(*args, **kwargs)
        except excClass, exc:
            excMsg = str(exc)
            if not msg:
                # No message provided: it passes.
                return  #pragma: no cover
            elif excMsg == msg:
                # Message provided, and we got the right message: it passes.
                return
            else:   #pragma: no cover
                # Message provided, and it didn't match: fail!
                raise self.failureException("Right exception, wrong message: got '%s' expected '%s'" % (excMsg, msg))
        # No need to catch other exceptions: They'll fail the test all by themselves!
        else:   #pragma: no cover
            if hasattr(excClass,'__name__'):
                excName = excClass.__name__
            else:
                excName = str(excClass)
            raise self.failureException("Expected to raise %s, didn't get an exception at all" % excName)

    def nice_file(self, *fparts):
        return os.path.normcase(os.path.abspath(os.path.realpath(os.path.join(*fparts))))
    
    def run_command(self, cmd):
        """ Run the command-line `cmd`, print its output.
        """
        # Add our test modules directory to PYTHONPATH.  I'm sure there's too
        # much path munging here, but...
        here = os.path.dirname(self.nice_file(coverage.__file__, ".."))
        testmods = self.nice_file(here, 'test/modules')
        zipfile = self.nice_file(here, 'test/zipmods.zip')
        pypath = os.environ['PYTHONPATH']
        if pypath:
            pypath += os.pathsep
        pypath += testmods + os.pathsep + zipfile
        os.environ['PYTHONPATH'] = pypath
        
        stdin, stdouterr = os.popen4(cmd)
        output = stdouterr.read()
        if showstdout:
            print output
        return output


class BasicCoverageTests(CoverageTest):
    def testSimple(self):
        self.checkCoverage("""\
            a = 1
            b = 2
            
            c = 4
            # Nothing here
            d = 6
            """,
            [1,2,4,6], report="4 4 100%")
        
    def testIndentationWackiness(self):
        # Partial final lines are OK.
        self.checkCoverage("""\
            import sys
            if not sys.path:
                a = 1
                """,
            [1,2,3], "3")

    def testMultilineInitializer(self):
        self.checkCoverage("""\
            d = {
                'foo': 1+2,
                'bar': (lambda x: x+1)(1),
                'baz': str(1),
            }

            e = { 'foo': 1, 'bar': 2 }
            """,
            [1,7], "")

    def testListComprehension(self):
        self.checkCoverage("""\
            l = [
                2*i for i in range(10)
                if i > 5
                ]
            assert l == [12, 14, 16, 18]
            """,
            [1,5], "")
        

class SimpleStatementTests(CoverageTest):
    def testExpression(self):
        self.checkCoverage("""\
            1 + 2
            1 + \\
                2
            """,
            [1,2], "")

    def testAssert(self):
        self.checkCoverage("""\
            assert (1 + 2)
            assert (1 + 
                2)
            assert (1 + 2), 'the universe is broken'
            assert (1 +
                2), \\
                'something is amiss'
            """,
            [1,2,4,5], "")

    def testAssignment(self):
        # Simple variable assignment
        self.checkCoverage("""\
            a = (1 + 2)
            b = (1 +
                2)
            c = \\
                1
            """,
            [1,2,4], "")

    def testAssignTuple(self):
        self.checkCoverage("""\
            a = 1
            a,b,c = 7,8,9
            assert a == 7 and b == 8 and c == 9
            """,
            [1,2,3], "")
            
    def testAttributeAssignment(self):
        # Attribute assignment
        self.checkCoverage("""\
            class obj: pass
            o = obj()
            o.foo = (1 + 2)
            o.foo = (1 +
                2)
            o.foo = \\
                1
            """,
            [1,2,3,4,6], "")
        
    def testListofAttributeAssignment(self):
        self.checkCoverage("""\
            class obj: pass
            o = obj()
            o.a, o.b = (1 + 2), 3
            o.a, o.b = (1 +
                2), (3 +
                4)
            o.a, o.b = \\
                1, \\
                2
            """,
            [1,2,3,4,7], "")
        
    def testAugmentedAssignment(self):
        self.checkCoverage("""\
            a = 1
            a += 1
            a += (1 +
                2)
            a += \\
                1
            """,
            [1,2,3,5], "")

    def testTripleStringStuff(self):
        self.checkCoverage("""\
            a = '''
                a multiline
                string.
                '''
            b = '''
                long expression
                ''' + '''
                on many
                lines.
                '''
            c = len('''
                long expression
                ''' + 
                '''
                on many
                lines.
                ''')
            """,
            [1,5,11], "")

    def testPass(self):
        # pass is tricky: if it's the only statement in a block, then it is
        # "executed". But if it is not the only statement, then it is not.
        self.checkCoverage("""\
            if 1==1:
                pass
            """,
            [1,2], "")
        self.checkCoverage("""\
            def foo():
                pass
            foo()
            """,
            [1,2,3], "")
        self.checkCoverage("""\
            def foo():
                "doc"
                pass
            foo()
            """,
            ([1,3,4], [1,4]), "")
        self.checkCoverage("""\
            class Foo:
                def foo(self):
                    pass
            Foo().foo()
            """,
            [1,2,3,4], "")
        self.checkCoverage("""\
            class Foo:
                def foo(self):
                    "Huh?"
                    pass
            Foo().foo()
            """,
            ([1,2,4,5], [1,2,5]), "")
        
    def testDel(self):
        self.checkCoverage("""\
            d = { 'a': 1, 'b': 1, 'c': 1, 'd': 1, 'e': 1 }
            del d['a']
            del d[
                'b'
                ]
            del d['c'], \\
                d['d'], \\
                d['e']
            assert(len(d.keys()) == 0)
            """,
            [1,2,3,6,9], "")

    def testPrint(self):
        self.checkCoverage("""\
            print "hello, world!"
            print ("hey: %d" %
                17)
            print "goodbye"
            print "hello, world!",
            print ("hey: %d" %
                17),
            print "goodbye",
            """,
            [1,2,4,5,6,8], "")
        
    def testRaise(self):
        self.checkCoverage("""\
            try:
                raise Exception(
                    "hello %d" %
                    17)
            except:
                pass
            """,
            [1,2,5,6], "")

    def testReturn(self):
        self.checkCoverage("""\
            def fn():
                a = 1
                return a

            x = fn()
            assert(x == 1)
            """,
            [1,2,3,5,6], "")
        self.checkCoverage("""\
            def fn():
                a = 1
                return (
                    a +
                    1)
                    
            x = fn()
            assert(x == 2)
            """,
            [1,2,3,7,8], "")
        self.checkCoverage("""\
            def fn():
                a = 1
                return (a,
                    a + 1,
                    a + 2)
                    
            x,y,z = fn()
            assert x == 1 and y == 2 and z == 3
            """,
            [1,2,3,7,8], "")

    def testYield(self):
        self.checkCoverage("""\
            from __future__ import generators
            def gen():
                yield 1
                yield (2+
                    3+
                    4)
                yield 1, \\
                    2
            a,b,c = gen()
            assert a == 1 and b == 9 and c == (1,2)
            """,
            [1,2,3,4,7,9,10], "")
        
    def testBreak(self):
        self.checkCoverage("""\
            for x in range(10):
                print "Hello"
                break
                print "Not here"
            """,
            [1,2,3,4], "4")
        
    def testContinue(self):
        self.checkCoverage("""\
            for x in range(10):
                print "Hello"
                continue
                print "Not here"
            """,
            [1,2,3,4], "4")
    
    if 0:
        # Peephole optimization of jumps to jumps can mean that some statements
        # never hit the line tracer.  The behavior is different in different
        # versions of Python, so don't run this test:
        def testStrangeUnexecutedContinue(self):
            self.checkCoverage("""\
                a = b = c = 0
                for n in range(100):
                    if n % 2:
                        if n % 4:
                            a += 1
                        continue    # <-- This line may not be hit.
                    else:
                        b += 1
                    c += 1
                assert a == 50 and b == 50 and c == 50
                
                a = b = c = 0
                for n in range(100):
                    if n % 2:
                        if n % 3:
                            a += 1
                        continue    # <-- This line is always hit.
                    else:
                        b += 1
                    c += 1
                assert a == 33 and b == 50 and c == 50
                """,
                [1,2,3,4,5,6,8,9,10, 12,13,14,15,16,17,19,20,21], "")
        
    def testImport(self):
        self.checkCoverage("""\
            import string
            from sys import path
            a = 1
            """,
            [1,2,3], "")
        self.checkCoverage("""\
            import string
            if 1 == 2:
                from sys import path
            a = 1
            """,
            [1,2,3,4], "3")
        self.checkCoverage("""\
            import string, \\
                os, \\
                re
            from sys import path, \\
                stdout
            a = 1
            """,
            [1,4,6], "")
        self.checkCoverage("""\
            import sys, sys as s
            assert s.path == sys.path
            """,
            [1,2], "")
        self.checkCoverage("""\
            import sys, \\
                sys as s
            assert s.path == sys.path
            """,
            [1,3], "")
        self.checkCoverage("""\
            from sys import path, \\
                path as p
            assert p == path
            """,
            [1,3], "")
        self.checkCoverage("""\
            from sys import \\
                *
            assert len(path) > 0
            """,
            [1,3], "")
        
    def testGlobal(self):
        self.checkCoverage("""\
            g = h = i = 1
            def fn():
                global g
                global h, \\
                    i
                g = h = i = 2
            fn()
            assert g == 2 and h == 2 and i == 2
            """,
            [1,2,6,7,8], "")
        self.checkCoverage("""\
            g = h = i = 1
            def fn():
                global g; g = 2
            fn()
            assert g == 2 and h == 1 and i == 1
            """,
            [1,2,3,4,5], "")

    def testExec(self):
        self.checkCoverage("""\
            a = b = c = 1
            exec "a = 2"
            exec ("b = " +
                "c = " +
                "2")
            assert a == 2 and b == 2 and c == 2
            """,
            [1,2,3,6], "")
        self.checkCoverage("""\
            vars = {'a': 1, 'b': 1, 'c': 1}
            exec "a = 2" in vars
            exec ("b = " +
                "c = " +
                "2") in vars
            assert vars['a'] == 2 and vars['b'] == 2 and vars['c'] == 2
            """,
            [1,2,3,6], "")
        self.checkCoverage("""\
            globs = {}
            locs = {'a': 1, 'b': 1, 'c': 1}
            exec "a = 2" in globs, locs
            exec ("b = " +
                "c = " +
                "2") in globs, locs
            assert locs['a'] == 2 and locs['b'] == 2 and locs['c'] == 2
            """,
            [1,2,3,4,7], "")

    def testExtraDocString(self):
        self.checkCoverage("""\
            a = 1
            "An extra docstring, should be a comment."
            b = 3
            assert (a,b) == (1,3)
            """,
            [1,3,4], "")
        self.checkCoverage("""\
            a = 1
            "An extra docstring, should be a comment."
            b = 3
            123 # A number for some reason: ignored
            1+1 # An expression: executed.
            c = 6
            assert (a,b,c) == (1,3,6)
            """,
            ([1,3,5,6,7], [1,3,4,5,6,7]), "")


class CompoundStatementTests(CoverageTest):
    def testStatementList(self):
        self.checkCoverage("""\
            a = 1;
            b = 2; c = 3
            d = 4; e = 5;
            
            assert (a,b,c,d,e) == (1,2,3,4,5)
            """,
            [1,2,3,5], "")
        
    def testIf(self):
        self.checkCoverage("""\
            a = 1
            if a == 1:
                x = 3
            assert x == 3
            if (a == 
                1):
                x = 7
            assert x == 7
            """,
            [1,2,3,4,5,7,8], "")
        self.checkCoverage("""\
            a = 1
            if a == 1:
                x = 3
            else:
                y = 5
            assert x == 3
            """,
            [1,2,3,5,6], "5")
        self.checkCoverage("""\
            a = 1
            if a != 1:
                x = 3
            else:
                y = 5
            assert y == 5
            """,
            [1,2,3,5,6], "3")
        self.checkCoverage("""\
            a = 1; b = 2
            if a == 1:
                if b == 2:
                    x = 4
                else:
                    y = 6
            else:
                z = 8
            assert x == 4
            """,
            [1,2,3,4,6,8,9], "6-8")
    
    def testElif(self):
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a == 1:
                x = 3
            elif b == 2:
                y = 5
            else:
                z = 7
            assert x == 3
            """,
            [1,2,3,4,5,7,8], "4-7", report="7 4 57% 4-7")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a != 1:
                x = 3
            elif b == 2:
                y = 5
            else:
                z = 7
            assert y == 5
            """,
            [1,2,3,4,5,7,8], "3, 7", report="7 5 71% 3, 7")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a != 1:
                x = 3
            elif b != 2:
                y = 5
            else:
                z = 7
            assert z == 7
            """,
            [1,2,3,4,5,7,8], "3, 5", report="7 5 71% 3, 5")

    def testElifNoElse(self):
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a == 1:
                x = 3
            elif b == 2:
                y = 5
            assert x == 3
            """,
            [1,2,3,4,5,6], "4-5", report="6 4 66% 4-5")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a != 1:
                x = 3
            elif b == 2:
                y = 5
            assert y == 5
            """,
            [1,2,3,4,5,6], "3", report="6 5 83% 3")

    def testElifBizarre(self):
        self.checkCoverage("""\
            def f(self):
                if self==1:
                    x = 3
                elif self.m('fred'):
                    x = 5
                elif (g==1) and (b==2):
                    x = 7
                elif self.m('fred')==True:
                    x = 9
                elif ((g==1) and (b==2))==True:
                    x = 11
                else:
                    x = 13
            """,
            [1,2,3,4,5,6,7,8,9,10,11,13], "2-13")

    def testSplitIf(self):
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if \\
                a == 1:
                x = 3
            elif \\
                b == 2:
                y = 5
            else:
                z = 7
            assert x == 3
            """,
            [1,2,4,5,7,9,10], "5-9")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if \\
                a != 1:
                x = 3
            elif \\
                b == 2:
                y = 5
            else:
                z = 7
            assert y == 5
            """,
            [1,2,4,5,7,9,10], "4, 9")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if \\
                a != 1:
                x = 3
            elif \\
                b != 2:
                y = 5
            else:
                z = 7
            assert z == 7
            """,
            [1,2,4,5,7,9,10], "4, 7")
        
    def testPathologicalSplitIf(self):
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if (
                a == 1
                ):
                x = 3
            elif (
                b == 2
                ):
                y = 5
            else:
                z = 7
            assert x == 3
            """,
            [1,2,5,6,9,11,12], "6-11")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if (
                a != 1
                ):
                x = 3
            elif (
                b == 2
                ):
                y = 5
            else:
                z = 7
            assert y == 5
            """,
            [1,2,5,6,9,11,12], "5, 11")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if (
                a != 1
                ):
                x = 3
            elif (
                b != 2
                ):
                y = 5
            else:
                z = 7
            assert z == 7
            """,
            [1,2,5,6,9,11,12], "5, 9")
        
    def testAbsurdSplitIf(self):
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a == 1 \\
                :
                x = 3
            elif b == 2 \\
                :
                y = 5
            else:
                z = 7
            assert x == 3
            """,
            [1,2,4,5,7,9,10], "5-9")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a != 1 \\
                :
                x = 3
            elif b == 2 \\
                :
                y = 5
            else:
                z = 7
            assert y == 5
            """,
            [1,2,4,5,7,9,10], "4, 9")
        self.checkCoverage("""\
            a = 1; b = 2; c = 3;
            if a != 1 \\
                :
                x = 3
            elif b != 2 \\
                :
                y = 5
            else:
                z = 7
            assert z == 7
            """,
            [1,2,4,5,7,9,10], "4, 7")

    def testWhile(self):
        self.checkCoverage("""\
            a = 3; b = 0
            while a:
                b += 1
                a -= 1
            assert a == 0 and b == 3
            """,
            [1,2,3,4,5], "")
        self.checkCoverage("""\
            a = 3; b = 0
            while a:
                b += 1
                break
                b = 99
            assert a == 3 and b == 1
            """,
            [1,2,3,4,5,6], "5")

    def testWhileElse(self):
        # Take the else branch.
        self.checkCoverage("""\
            a = 3; b = 0
            while a:
                b += 1
                a -= 1
            else:
                b = 99
            assert a == 0 and b == 99
            """,
            [1,2,3,4,6,7], "")
        # Don't take the else branch.
        self.checkCoverage("""\
            a = 3; b = 0
            while a:
                b += 1
                a -= 1
                break
                b = 123
            else:
                b = 99
            assert a == 2 and b == 1
            """,
            [1,2,3,4,5,6,8,9], "6-8")
    
    def testSplitWhile(self):
        self.checkCoverage("""\
            a = 3; b = 0
            while \\
                a:
                b += 1
                a -= 1
            assert a == 0 and b == 3
            """,
            [1,2,4,5,6], "")
        self.checkCoverage("""\
            a = 3; b = 0
            while (
                a
                ):
                b += 1
                a -= 1
            assert a == 0 and b == 3
            """,
            [1,2,5,6,7], "")

    def testFor(self):
        self.checkCoverage("""\
            a = 0
            for i in [1,2,3,4,5]:
                a += i
            assert a == 15
            """,
            [1,2,3,4], "")
        self.checkCoverage("""\
            a = 0
            for i in [1,
                2,3,4,
                5]:
                a += i
            assert a == 15
            """,
            [1,2,5,6], "")
        self.checkCoverage("""\
            a = 0
            for i in [1,2,3,4,5]:
                a += i
                break
                a = 99
            assert a == 1
            """,
            [1,2,3,4,5,6], "5")
    
    def testForElse(self):
        self.checkCoverage("""\
            a = 0
            for i in range(5):
                a += i+1
            else:
                a = 99
            assert a == 99
            """,
            [1,2,3,5,6], "")
        self.checkCoverage("""\
            a = 0
            for i in range(5):
                a += i+1
                break
                a = 99
            else:
                a = 123
            assert a == 1
            """,
            [1,2,3,4,5,7,8], "5-7")
    
    def testSplitFor(self):
        self.checkCoverage("""\
            a = 0
            for \\
                i in [1,2,3,4,5]:
                a += i
            assert a == 15
            """,
            [1,2,4,5], "")
        self.checkCoverage("""\
            a = 0
            for \\
                i in [1,
                2,3,4,
                5]:
                a += i
            assert a == 15
            """,
            [1,2,6,7], "")
    
    def testTryExcept(self):
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
            except:
                a = 99
            assert a == 1
            """,
            [1,2,3,4,5,6], "4-5")
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except:
                a = 99
            assert a == 99
            """,
            [1,2,3,4,5,6,7], "")
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except ImportError:
                a = 99
            except:
                a = 123
            assert a == 123
            """,
            [1,2,3,4,5,6,7,8,9], "6")
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise IOError("foo")
            except ImportError:
                a = 99
            except IOError:
                a = 17
            except:
                a = 123
            assert a == 17
            """,
            [1,2,3,4,5,6,7,8,9,10,11], "6, 9-10")
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
            except:
                a = 99
            else:
                a = 123
            assert a == 123
            """,
            [1,2,3,4,5,7,8], "4-5")
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except:
                a = 99
            else:
                a = 123
            assert a == 99
            """,
            [1,2,3,4,5,6,8,9], "8")
    
    def testTryFinally(self):
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
            finally:
                a = 99
            assert a == 99
            """,
            [1,2,3,5,6], "")
        self.checkCoverage("""\
            a = 0; b = 0
            try:
                a = 1
                try:
                    raise Exception("foo")
                finally:
                    b = 123
            except:
                a = 99
            assert a == 99 and b == 123
            """,
            [1,2,3,4,5,7,8,9,10], "")

    def testFunctionDef(self):
        self.checkCoverage("""\
            a = 99
            def foo():
                ''' docstring
                '''
                return 1
                
            a = foo()
            assert a == 1
            """,
            [1,2,5,7,8], "")
        self.checkCoverage("""\
            def foo(
                a,
                b
                ):
                ''' docstring
                '''
                return a+b
                
            x = foo(17, 23)
            assert x == 40
            """,
            [1,7,9,10], "")
        self.checkCoverage("""\
            def foo(
                a = (lambda x: x*2)(10),
                b = (
                    lambda x:
                        x+1
                    )(1)
                ):
                ''' docstring
                '''
                return a+b
                
            x = foo()
            assert x == 22
            """,
            [1,10,12,13], "")

    def testClassDef(self):
        self.checkCoverage("""\
            # A comment.
            class theClass:
                ''' the docstring.
                    Don't be fooled.
                '''
                def __init__(self):
                    ''' Another docstring. '''
                    self.a = 1
                
                def foo(self):
                    return self.a
            
            x = theClass().foo()
            assert x == 1
            """,
            [2,6,8,10,11,13,14], "")    


class ExcludeTests(CoverageTest):
    def testSimple(self):
        self.checkCoverage("""\
            a = 1; b = 2

            if 0:
                a = 4   # -cc
            """,
            [1,3], "", ['-cc'])

    def testTwoExcludes(self):
        self.checkCoverage("""\
            a = 1; b = 2

            if a == 99:
                a = 4   # -cc
                b = 5
                c = 6   # -xx
            assert a == 1 and b == 2
            """,
            [1,3,5,7], "5", ['-cc', '-xx'])
        
    def testExcludingIfSuite(self):
        self.checkCoverage("""\
            a = 1; b = 2

            if 0:
                a = 4
                b = 5
                c = 6
            assert a == 1 and b == 2
            """,
            [1,7], "", ['if 0:'])

    def testExcludingIfButNotElseSuite(self):
        self.checkCoverage("""\
            a = 1; b = 2

            if 0:
                a = 4
                b = 5
                c = 6
            else:
                a = 8
                b = 9
            assert a == 8 and b == 9
            """,
            [1,8,9,10], "", ['if 0:'])
        
    def testExcludingElseSuite(self):
        self.checkCoverage("""\
            a = 1; b = 2

            if 1==1:
                a = 4
                b = 5
                c = 6
            else:          #pragma: NO COVER
                a = 8
                b = 9
            assert a == 4 and b == 5 and c == 6
            """,
            [1,3,4,5,6,10], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 1; b = 2

            if 1==1:
                a = 4
                b = 5
                c = 6
            
            # Lots of comments to confuse the else handler.
            # more.
            
            else:          #pragma: NO COVER

            # Comments here too.
            
                a = 8
                b = 9
            assert a == 4 and b == 5 and c == 6
            """,
            [1,3,4,5,6,17], "", ['#pragma: NO COVER'])

    def testExcludingElifSuites(self):
        self.checkCoverage("""\
            a = 1; b = 2

            if 1==1:
                a = 4
                b = 5
                c = 6
            elif 1==0:          #pragma: NO COVER
                a = 8
                b = 9
            else:          
                a = 11
                b = 12
            assert a == 4 and b == 5 and c == 6
            """,
            [1,3,4,5,6,11,12,13], "11-12", ['#pragma: NO COVER'])

    def testExcludingOnelineIf(self):
        self.checkCoverage("""\
            def foo():
                a = 2
                if 0: x = 3     # no cover
                b = 4
                
            foo()
            """,
            [1,2,4,6], "", ["no cover"])

    def testExcludingAColonNotASuite(self):
        self.checkCoverage("""\
            def foo():
                l = range(10)
                print l[:3]   # no cover
                b = 4
                
            foo()
            """,
            [1,2,4,6], "", ["no cover"])
        
    def testExcludingForSuite(self):
        self.checkCoverage("""\
            a = 0
            for i in [1,2,3,4,5]:     #pragma: NO COVER
                a += i
            assert a == 15
            """,
            [1,4], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            for i in [1,
                2,3,4,
                5]:                #pragma: NO COVER
                a += i
            assert a == 15
            """,
            [1,6], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            for i in [1,2,3,4,5
                ]:                        #pragma: NO COVER
                a += i
                break
                a = 99
            assert a == 1
            """,
            [1,7], "", ['#pragma: NO COVER'])
            
    def testExcludingForElse(self):
        self.checkCoverage("""\
            a = 0
            for i in range(5):
                a += i+1
                break
                a = 99
            else:               #pragma: NO COVER
                a = 123
            assert a == 1
            """,
            [1,2,3,4,5,8], "5", ['#pragma: NO COVER'])
    
    def testExcludingWhile(self):
        self.checkCoverage("""\
            a = 3; b = 0
            while a*b:           #pragma: NO COVER
                b += 1
                break
                b = 99
            assert a == 3 and b == 0
            """,
            [1,6], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 3; b = 0
            while (
                a*b
                ):           #pragma: NO COVER
                b += 1
                break
                b = 99
            assert a == 3 and b == 0
            """,
            [1,8], "", ['#pragma: NO COVER'])

    def testExcludingWhileElse(self):
        self.checkCoverage("""\
            a = 3; b = 0
            while a:
                b += 1
                break
                b = 99
            else:           #pragma: NO COVER
                b = 123
            assert a == 3 and b == 1
            """,
            [1,2,3,4,5,8], "5", ['#pragma: NO COVER'])

    def testExcludingTryExcept(self):
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
            except:           #pragma: NO COVER
                a = 99
            assert a == 1
            """,
            [1,2,3,6], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except:
                a = 99
            assert a == 99
            """,
            [1,2,3,4,5,6,7], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except ImportError:    #pragma: NO COVER
                a = 99
            except:
                a = 123
            assert a == 123
            """,
            [1,2,3,4,7,8,9], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
            except:       #pragma: NO COVER
                a = 99
            else:
                a = 123
            assert a == 123
            """,
            [1,2,3,7,8], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except:
                a = 99
            else:              #pragma: NO COVER
                a = 123
            assert a == 99
            """,
            [1,2,3,4,5,6,9], "", ['#pragma: NO COVER'])
    
    def testExcludingTryExceptPass(self):
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
            except:           #pragma: NO COVER
                x = 2
            assert a == 1
            """,
            [1,2,3,6], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except ImportError:    #pragma: NO COVER
                x = 2
            except:
                a = 123
            assert a == 123
            """,
            [1,2,3,4,7,8,9], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
            except:       #pragma: NO COVER
                x = 2
            else:
                a = 123
            assert a == 123
            """,
            [1,2,3,7,8], "", ['#pragma: NO COVER'])
        self.checkCoverage("""\
            a = 0
            try:
                a = 1
                raise Exception("foo")
            except:
                a = 99
            else:              #pragma: NO COVER
                x = 2
            assert a == 99
            """,
            [1,2,3,4,5,6,9], "", ['#pragma: NO COVER'])
    
    def testExcludingIfPass(self):
        # From a comment on the coverage page by Michael McNeil Forbes:
        self.checkCoverage("""\
            def f():
                if False:    # pragma: no cover
                    pass     # This line still reported as missing
                if False:    # pragma: no cover
                    x = 1    # Now it is skipped.
            
            f()
            """,
            [1,7], "", ["no cover"])
        
    def testExcludingFunction(self):
        self.checkCoverage("""\
            def fn(foo):      #pragma: NO COVER
                a = 1
                b = 2
                c = 3
                
            x = 1
            assert x == 1
            """,
            [6,7], "", ['#pragma: NO COVER'])

    def testExcludingMethod(self):
        self.checkCoverage("""\
            class Fooey:
                def __init__(self):
                    self.a = 1
                    
                def foo(self):     #pragma: NO COVER
                    return self.a
                    
            x = Fooey()
            assert x.a == 1
            """,
            [1,2,3,8,9], "", ['#pragma: NO COVER'])
        
    def testExcludingClass(self):
        self.checkCoverage("""\
            class Fooey:            #pragma: NO COVER
                def __init__(self):
                    self.a = 1
                    
                def foo(self):
                    return self.a
                    
            x = 1
            assert x == 1
            """,
            [8,9], "", ['#pragma: NO COVER'])


if sys.hexversion >= 0x020300f0:
    # threading support was new in 2.3, only test there.
    class ThreadingTests(CoverageTest):
        def testThreading(self):
            self.checkCoverage("""\
                import time, threading
    
                def fromMainThread():
                    return "called from main thread"
                
                def fromOtherThread():
                    return "called from other thread"
                
                def neverCalled():
                    return "no one calls me"
                
                threading.Thread(target=fromOtherThread).start()
                fromMainThread()
                time.sleep(1)
                """,
                [1,3,4,6,7,9,10,12,13,14], "10")


if sys.hexversion >= 0x020400f0:
    class Py24Tests(CoverageTest):
        def testFunctionDecorators(self):
            self.checkCoverage("""\
                def require_int(func):
                    def wrapper(arg):
                        assert isinstance(arg, int)
                        return func(arg)
                
                    return wrapper
                
                @require_int
                def p1(arg):
                    return arg*2
                
                assert p1(10) == 20
                """,
                [1,2,3,4,6,8,10,12], "")

        def testFunctionDecoratorsWithArgs(self):
            self.checkCoverage("""\
                def boost_by(extra):
                    def decorator(func):
                        def wrapper(arg):
                            return extra*func(arg)
                        return wrapper
                    return decorator
                
                @boost_by(10)
                def boosted(arg):
                    return arg*2
                
                assert boosted(10) == 200
                """,
                [1,2,3,4,5,6,8,10,12], "")

        def testDoubleFunctionDecorators(self):
            self.checkCoverage("""\
                def require_int(func):
                    def wrapper(arg):
                        assert isinstance(arg, int)
                        return func(arg)
                    return wrapper

                def boost_by(extra):
                    def decorator(func):
                        def wrapper(arg):
                            return extra*func(arg)
                        return wrapper
                    return decorator
                
                @require_int
                @boost_by(10)
                def boosted1(arg):
                    return arg*2
                
                assert boosted1(10) == 200

                @boost_by(10)
                @require_int
                def boosted2(arg):
                    return arg*2
                
                assert boosted2(10) == 200
                """,
                ([1,2,3,4,5,7,8,9,10,11,12,14,15,17,19,21,22,24,26],
                 [1,2,3,4,5,7,8,9,10,11,12,14,   17,19,21,   24,26]), "")


if sys.hexversion >= 0x020500f0:
    class Py25Tests(CoverageTest):
        def testWithStatement(self):
            self.checkCoverage("""\
                from __future__ import with_statement
                
                class Managed:
                    def __enter__(self):
                        print "enter"
                        
                    def __exit__(self, type, value, tb):
                        print "exit", type
                        
                m = Managed()
                with m:
                    print "block1a"
                    print "block1b"
                    
                try:
                    with m:
                        print "block2"
                        raise Exception("Boo!")
                except:
                    print "caught"
                """,
                [1,3,4,5,7,8,10,11,12,13,15,16,17,18,19,20], "")
    
        def testTryExceptFinally(self):
            self.checkCoverage("""\
                a = 0; b = 0
                try:
                    a = 1
                except:
                    a = 99
                finally:
                    b = 2
                assert a == 1 and b == 2
                """,
                [1,2,3,4,5,7,8], "4-5")
            self.checkCoverage("""\
                a = 0; b = 0
                try:
                    a = 1
                    raise Exception("foo")
                except:
                    a = 99
                finally:
                    b = 2
                assert a == 99 and b == 2
                """,
                [1,2,3,4,5,6,8,9], "")
            self.checkCoverage("""\
                a = 0; b = 0
                try:
                    a = 1
                    raise Exception("foo")
                except ImportError:
                    a = 99
                except:
                    a = 123
                finally:
                    b = 2
                assert a == 123 and b == 2
                """,
                [1,2,3,4,5,6,7,8,10,11], "6")
            self.checkCoverage("""\
                a = 0; b = 0
                try:
                    a = 1
                    raise IOError("foo")
                except ImportError:
                    a = 99
                except IOError:
                    a = 17
                except:
                    a = 123
                finally:
                    b = 2
                assert a == 17 and b == 2
                """,
                [1,2,3,4,5,6,7,8,9,10,12,13], "6, 9-10")
            self.checkCoverage("""\
                a = 0; b = 0
                try:
                    a = 1
                except:
                    a = 99
                else:
                    a = 123
                finally:
                    b = 2
                assert a == 123 and b == 2
                """,
                [1,2,3,4,5,7,9,10], "4-5")
            self.checkCoverage("""\
                a = 0; b = 0
                try:
                    a = 1
                    raise Exception("foo")
                except:
                    a = 99
                else:
                    a = 123
                finally:
                    b = 2
                assert a == 99 and b == 2
                """,
                [1,2,3,4,5,6,8,10,11], "8")
        

class ModuleTests(CoverageTest):
    def testNotSingleton(self):
        """ You *can* create another coverage object.
        """
        coverage.coverage()
        coverage.coverage()


class ApiTests(CoverageTest):
    def testSimple(self):
        coverage.erase()

        self.makeFile("mycode", """\
            a = 1
            b = 2
            if b == 3:
                c = 4
            d = 5
            """)
            
        # Import the python file, executing it.
        coverage.start()
        self.importModule("mycode")
        coverage.stop()
    
        filename, statements, missing, readablemissing = coverage.analysis("mycode.py")
        self.assertEqual(statements, [1,2,3,4,5])
        self.assertEqual(missing, [4])
        self.assertEqual(readablemissing, "4")
        
    def doReportWork(self, modname):
        coverage.erase()

        self.makeFile(modname, """\
            a = 1
            b = 2
            if b == 3:
                c = 4
                d = 5
                e = 6
            f = 7
            """)
            
        # Import the python file, executing it.
        coverage.start()
        self.importModule(modname)
        coverage.stop()
        coverage.analysis(modname + ".py")
        
    def testReport(self):
        self.doReportWork("mycode2")
        coverage.report(["mycode2.py"])
        self.assertEqual(self.getStdout(), dedent("""\
            Name      Stmts   Exec  Cover   Missing
            ---------------------------------------
            mycode2       7      4    57%   4-6
            """))

    def testReportFile(self):
        self.doReportWork("mycode3")
        fout = StringIO()
        coverage.report(["mycode3.py"], file=fout)
        self.assertEqual(self.getStdout(), "")
        self.assertEqual(fout.getvalue(), dedent("""\
            Name      Stmts   Exec  Cover   Missing
            ---------------------------------------
            mycode3       7      4    57%   4-6
            """))


class AnnotationTests(CoverageTest):
    def testWhite(self):
        self.checkEverything(file='test/white.py', annfile='test/white.py,cover')


class CmdLineTests(CoverageTest):
    def help_fn(self, error=None):
        raise Exception(error or "__doc__")

    def command_line(self, argv):
        return coverage.CoverageScript().command_line(argv, self.help_fn)

    def testHelp(self):
        self.assertRaisesMsg(Exception, "__doc__", self.command_line, ['-h'])
        self.assertRaisesMsg(Exception, "__doc__", self.command_line, ['--help'])

    def testUnknownOption(self):
        self.assertRaisesMsg(Exception, "option -z not recognized", self.command_line, ['-z'])

    def testBadActionCombinations(self):
        self.assertRaisesMsg(Exception, "You can't specify the 'erase' and 'annotate' options at the same time.", self.command_line, ['-e', '-a'])
        self.assertRaisesMsg(Exception, "You can't specify the 'erase' and 'report' options at the same time.", self.command_line, ['-e', '-r'])
        self.assertRaisesMsg(Exception, "You can't specify the 'erase' and 'combine' options at the same time.", self.command_line, ['-e', '-c'])
        self.assertRaisesMsg(Exception, "You can't specify the 'execute' and 'annotate' options at the same time.", self.command_line, ['-x', '-a'])
        self.assertRaisesMsg(Exception, "You can't specify the 'execute' and 'report' options at the same time.", self.command_line, ['-x', '-r'])
        self.assertRaisesMsg(Exception, "You can't specify the 'execute' and 'combine' options at the same time.", self.command_line, ['-x', '-c'])

    def testNeedAction(self):
        self.assertRaisesMsg(Exception, "You must specify at least one of -e, -x, -c, -r, or -a.", self.command_line, ['-p'])

    def testArglessActions(self):
        self.assertRaisesMsg(Exception, "Unexpected arguments: foo bar", self.command_line, ['-e', 'foo', 'bar'])
        self.assertRaisesMsg(Exception, "Unexpected arguments: baz quux", self.command_line, ['-c', 'baz', 'quux'])


class ProcessTests(CoverageTest):
    def testSaveOnExit(self):
        self.makeFile("mycode", """\
            a = 1
            b = 2
            if b == 3:
                c = 4
            d = 5
            """)
            
        self.assert_(not os.path.exists(".coverage"))
        self.run_command("coverage -x mycode.py")
        self.assert_(os.path.exists(".coverage"))

    def testEnvironment(self):
        # Checks that we can import modules from the test directory at all!
        self.makeFile("mycode", """\
            import covmod1
            import covmodzip1
            a = 1
            print 'done'
            """)

        self.assert_(not os.path.exists(".coverage"))
        out = self.run_command("coverage -x mycode.py")
        self.assert_(os.path.exists(".coverage"))
        self.assertEqual(out, 'done\n')
    
    def testReport(self):
        self.makeFile("mycode", """\
            import covmod1
            import covmodzip1
            a = 1
            print 'done'
            """)

        out = self.run_command("coverage -x mycode.py")
        self.assertEqual(out, 'done\n')
        report1 = self.run_command("coverage -r").replace('\\', '/')

        # Name                                                Stmts   Exec  Cover
        # -----------------------------------------------------------------------
        # c:/ned/coverage/trunk/coverage/__init__               616      3     0%
        # c:/ned/coverage/trunk/test/modules/covmod1              2      2   100%
        # c:/ned/coverage/trunk/test/zipmods.zip/covmodzip1       2      2   100%
        # c:/python25/lib/atexit                                 33      5    15%
        # c:/python25/lib/ntpath                                250     12     4%
        # c:/python25/lib/threading                             562      1     0%
        # mycode                                                  4      4   100%
        # -----------------------------------------------------------------------
        # TOTAL                                                1467     27     1%

        self.assert_("/coverage/" in report1)
        self.assert_("/test/modules/covmod1 " in report1)
        self.assert_("/test/zipmods.zip/covmodzip1 " in report1)
        self.assert_("mycode " in report1)

        for l in report1.split('\n'):
            if '/test/modules/covmod1' in l:
                # Save a module prefix for the omit test later.
                prefix = l.split('/test/')[0] + '/test/'
                break

        # Try reporting just one module
        report2 = self.run_command("coverage -r mycode.py").replace('\\', '/')
        self.assert_("/coverage/" not in report2)
        self.assert_("/test/modules/covmod1 " not in report2)
        self.assert_("/test/zipmods.zip/covmodzip1 " not in report2)
        self.assert_("mycode " in report2)

        # Try reporting while omitting some modules
        report3 = self.run_command("coverage -r -o %s" % prefix).replace('\\', '/')
        self.assert_("/coverage/" in report3)
        self.assert_("/test/modules/covmod1 " not in report3)
        self.assert_("/test/zipmods.zip/covmodzip1 " not in report3)
        self.assert_("mycode " in report3)

    def testCombineParallelData(self):
        self.makeFile("b_or_c", """\
            import sys
            a = 1
            if sys.argv[1] == 'b':
                b = 1
            else:
                c = 1
            d = 1
            print 'done'
            """)
        
        out = self.run_command("coverage -x -p b_or_c.py b")
        self.assertEqual(out, 'done\n')
        self.assert_(not os.path.exists(".coverage"))

        out = self.run_command("coverage -x -p b_or_c.py c")
        self.assertEqual(out, 'done\n')
        self.assert_(not os.path.exists(".coverage"))
        
        # After two -p runs, there should be two .coverage.machine.123 files.
        self.assertEqual(len([f for f in os.listdir('.') if f.startswith('.coverage.')]), 2)

        # Combine the parallel coverage data files into .coverage .
        self.run_command("coverage -c")
        self.assert_(os.path.exists(".coverage"))

        # Read the coverage file and see that b_or_c.py has all 7 lines executed.
        data = coverage.CoverageData()
        data.read_file(".coverage")
        self.assertEqual(data.summary()['b_or_c.py'], 7)


if __name__ == '__main__':
    print "Testing under Python version: %s" % sys.version
    unittest.main()


# TODO: split "and" conditions across lines, and detect not running lines.
#         (Can't be done: trace function doesn't get called for each line
#         in an expression!)
# TODO: Generator comprehensions? 
# TODO: Constant if tests ("if 1:").  Py 2.4 doesn't execute them.