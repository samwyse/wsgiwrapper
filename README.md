I create a lot of tools to help me get my job done quickly and efficiently. These tools are generally command-line driven (because I am a follower of the [UNIX philosophy](https://en.wikipedia.org/wiki/Unix_philosophy)) and are written in Python (because it is the [best language](https://www.techrepublic.com/resource-library/whitepapers/python-is-eating-the-world-how-one-developer-s-side-project-became-the-hottest-programming-language-on-the-planet-cover-story-pdf/) for creating such tools). The only problem (and it is a good problem to have) is that non-programmers see me using my tools and wish to use them themselves, preferably via a web GUI.

This tool will turn command line Python scripts into WSGI web applications. The original script is used unchanged; the only requirement is that you must adhere to a certain style of programming.

Here's a simple example of what's needed:

    def main():
        parser = mk_parser()
        args = parser.parse_args()
        return process(args)

To turn this into a WSGI app, you have two choices.  The first is to run
wsgiwrapper as an application.  This choice is probably better during
testing, as it uses wsgiref.simple_server to create a local server.

    usage: __main__.py [-h] [-v] -m MOD [-p PARSER] [-r PROCESS] [-s GROUP] [-u]
                       [-x PREFIX] [-H HOST] [-P PORT]

    Documentation

    optional arguments:
      -h, --help            show this help message and exit
      -v, --version         show program's version number and exit

    Wrapper configuration:
      Specify how to create the web application.

      -m MOD, --module MOD  The command line program to run as a WSGI app. This is
                            required.
      -p PARSER, --parser PARSER
                            The function that returns an argparser object; default
                            is mk_parser. The parser will be invoked once during
                            WSGI initialization. Defaults to "mk_parser".
      -r PROCESS, --run PROCESS
                            The function to run when the form is submitted;
                            default is process. This procedure can be invoked
                            multiple times during the lifetims of the WSGI app.
                            Defaults to "process."
      -s GROUP, --skip GROUP
                            Specify any parser groups to skip when building the
                            form. Note that 'help' and 'version' actions generate
                            special submission buttons and are visually removed
                            from their group(s). If this results in an empty
                            group, it is also not displayed.
      -u, --use-tables      Generate HTML using tables instead of "display=grid".
      -x PREFIX, --prefix PREFIX
                            If set, adds prefixed "environ" and "start_response"
                            to the wrapped application's arguments. This provides
                            a hint to the application that it is running as a
                            WSGI; this allows the application to, for example,
                            format it's output as HTML.

    Server configuration:
      Specify web server characteristics.

      -H HOST, --host HOST  The IP address to bind to the socket; default is
                            0.0.0.0.
      -P PORT, --port PORT  The port number to bind to the socket; default is
                            8080.

The other choice is to write a wrapper script to create an app object,
which can be handed off to any WSGI-compliant server.

    from wsgiwrapper import wsgiwrapper
    import example
    
    app = wsgiwrapper(
        example.mk_parser(),
        example.process)
