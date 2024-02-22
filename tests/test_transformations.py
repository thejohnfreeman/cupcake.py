import io
import textwrap

from cupcake import transformations as tf

def mls(string):
    return textwrap.dedent(string).strip('\n')

def test_remove_includes():
    sin = mls("""
    /**
     * This is a source file.
     */

        #define NDEBUG
    /*
    #include <abc/abc.hpp>
    */
        //#include <abc/abc.hpp>
    #include <abc/abc.hpp> // only this line should be removed
    #include <def/def.hpp>

    int one = 1;
    """)
    sout = io.StringIO()
    expected = mls("""
    /**
     * This is a source file.
     */

        #define NDEBUG
    /*
    #include <abc/abc.hpp>
    */
        //#include <abc/abc.hpp>
    #include <def/def.hpp>

    int one = 1;
    """)
    tf._remove_includes(iter(sin.splitlines(keepends=True)), sout, 'abc')
    assert(sout.getvalue() == expected)
