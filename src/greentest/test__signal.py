from __future__ import print_function
import signal
import greentest
import gevent
import pkg_resources

try:
    cffi_version = pkg_resources.get_distribution('cffi').parsed_version
except Exception:
    # No cffi installed. Shouldn't happen to gevent standard tests,
    # but maybe some downstream distributor removed it.
    cffi_version = None

class Expected(Exception):
    pass


def raise_Expected():
    raise Expected('TestSignal')


if hasattr(signal, 'SIGALRM'):

    class TestSignal(greentest.TestCase):

        error_fatal = False
        __timeout__ = greentest.LARGE_TIMEOUT

        def test_handler(self):
            self.assertRaises(TypeError, gevent.signal, signal.SIGALRM, 1)

        def test_alarm(self):
            sig = gevent.signal(signal.SIGALRM, raise_Expected)
            assert sig.ref is False, repr(sig.ref)
            sig.ref = True
            assert sig.ref is True
            sig.ref = False
            try:
                signal.alarm(1)
                try:
                    gevent.sleep(2)
                    raise AssertionError('must raise Expected')
                except Expected as ex:
                    assert str(ex) == 'TestSignal', ex
                # also let's check that alarm is persistent
                signal.alarm(1)
                try:
                    gevent.sleep(2)
                    raise AssertionError('must raise Expected')
                except Expected as ex:
                    assert str(ex) == 'TestSignal', ex
            finally:
                sig.cancel()


        @greentest.skipIf((greentest.PY3
                           and greentest.CFFI_BACKEND
                           and cffi_version < pkg_resources.parse_version('1.11.3')),
                          "https://bitbucket.org/cffi/cffi/issues/352/systemerror-returned-a-result-with-an")
        @greentest.ignores_leakcheck
        def test_reload(self):
            # The site module tries to set attributes
            # on all the modules that are loaded (specifically, __file__).
            # If gevent.signal is loaded, and is our compatibility shim,
            # this used to fail on Python 2: sys.modules['gevent.signal'] has no
            # __loader__ attribute, so site.py's main() function tries to do
            # gevent.signal.__file__ = os.path.abspath(gevent.signal.__file__), which
            # used to not be allowed. (Under Python 3, __loader__ is present so this
            # doesn't happen). See
            # https://github.com/gevent/gevent/issues/805

            # This fails on Python 3.5 under linux (travis CI) but not
            # locally on macOS with (for both libuv and libev cffi); sometimes it
            # failed with libuv on Python 3.6 too, but not always:
            #   AttributeError: cffi library 'gevent.libuv._corecffi' has no function,
            #      constant or global variable named '__loader__'
            # which in turn leads to:
            #   SystemError: <built-in function getattr> returned a result with an error set

            # It's not safe to continue after a SystemError, so we just skip the test there.

            # As of Jan 2018 with CFFI 1.11.2 this happens reliably on macOS 3.6 and 3.7
            # as well.

            # See https://bitbucket.org/cffi/cffi/issues/352/systemerror-returned-a-result-with-an

            # This is fixed in 1.11.3

            import gevent.signal # make sure it's in sys.modules pylint:disable=redefined-outer-name
            assert gevent.signal
            import site
            if greentest.PY34:
                from importlib import reload as reload_module
            elif greentest.PY3:
                from imp import reload as reload_module
            else:
                # builtin on py2
                reload_module = reload # pylint:disable=undefined-variable

            try:
                reload_module(site)
            except TypeError:
                # Non-CFFI on Travis triggers this, for some reason,
                # but only on 3.6, not 3.4 or 3.5, and not yet on 3.7.

                # The only module seen to trigger this is __main__, i.e., this module.

                # This is hard to trigger in a virtualenv since it appears they
                # install their own site.py, different from the one that ships with
                # Python 3.6., and at least the version I have doesn't mess with
                # __cached__
                assert greentest.PY36
                import sys
                for m in set(sys.modules.values()):
                    try:
                        if m.__cached__ is None:
                            print("Module has None __cached__", m, file=sys.stderr)
                    except AttributeError:
                        continue

if __name__ == '__main__':
    greentest.main()
