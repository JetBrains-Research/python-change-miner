@if "%DEBUG%" == "" @echo off
@rem ##########################################################################
@rem
@rem  gumtree startup script for Windows
@rem
@rem ##########################################################################

@rem Set local scope for the variables with windows NT shell
if "%OS%"=="Windows_NT" setlocal

set DIRNAME=%~dp0
if "%DIRNAME%" == "" set DIRNAME=.
set APP_BASE_NAME=%~n0
set APP_HOME=%DIRNAME%..

@rem Add default JVM options here. You can also use JAVA_OPTS and GUMTREE_OPTS to pass JVM options to this script.
set DEFAULT_JVM_OPTS=

@rem Find java.exe
if defined JAVA_HOME goto findJavaFromJavaHome

set JAVA_EXE=java.exe
%JAVA_EXE% -version >NUL 2>&1
if "%ERRORLEVEL%" == "0" goto init

echo.
echo ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.
echo.
echo Please set the JAVA_HOME variable in your environment to match the
echo location of your Java installation.

goto fail

:findJavaFromJavaHome
set JAVA_HOME=%JAVA_HOME:"=%
set JAVA_EXE=%JAVA_HOME%/bin/java.exe

if exist "%JAVA_EXE%" goto init

echo.
echo ERROR: JAVA_HOME is set to an invalid directory: %JAVA_HOME%
echo.
echo Please set the JAVA_HOME variable in your environment to match the
echo location of your Java installation.

goto fail

:init
@rem Get command-line arguments, handling Windows variants

if not "%OS%" == "Windows_NT" goto win9xME_args

:win9xME_args
@rem Slurp the command line arguments.
set CMD_LINE_ARGS=
set _SKIP=2

:win9xME_args_slurp
if "x%~1" == "x" goto execute

set CMD_LINE_ARGS=%*

:execute
@rem Setup the command line

set CLASSPATH=%APP_HOME%\lib\gumtree-2.1.2.jar;%APP_HOME%\lib\client.diff-2.1.2.jar;%APP_HOME%\lib\client-2.1.2.jar;%APP_HOME%\lib\gen.antlr3-antlr-2.1.2.jar;%APP_HOME%\lib\gen.antlr3-json-2.1.2.jar;%APP_HOME%\lib\gen.antlr3-php-2.1.2.jar;%APP_HOME%\lib\gen.antlr3-r-2.1.2.jar;%APP_HOME%\lib\gen.antlr3-xml-2.1.2.jar;%APP_HOME%\lib\gen.antlr3-2.1.2.jar;%APP_HOME%\lib\gen.c-2.1.2.jar;%APP_HOME%\lib\gen.css-2.1.2.jar;%APP_HOME%\lib\gen.javaparser-2.1.2.jar;%APP_HOME%\lib\gen.jdt-2.1.2.jar;%APP_HOME%\lib\gen.js-2.1.2.jar;%APP_HOME%\lib\gen.python-2.1.2.jar;%APP_HOME%\lib\gen.ruby-2.1.2.jar;%APP_HOME%\lib\gen.srcml-2.1.2.jar;%APP_HOME%\lib\core-2.1.2.jar;%APP_HOME%\lib\classindex-3.4.jar;%APP_HOME%\lib\simmetrics-core-3.2.3.jar;%APP_HOME%\lib\trove4j-3.0.3.jar;%APP_HOME%\lib\gson-2.8.2.jar;%APP_HOME%\lib\jgrapht-core-1.0.1.jar;%APP_HOME%\lib\spark-core-2.7.1.jar;%APP_HOME%\lib\slf4j-nop-1.7.25.jar;%APP_HOME%\lib\rendersnake-1.9.0.jar;%APP_HOME%\lib\antlr-3.5.2.jar;%APP_HOME%\lib\ph-css-6.1.2.jar;%APP_HOME%\lib\javaparser-symbol-solver-core-3.13.1.jar;%APP_HOME%\lib\org.eclipse.jdt.core-3.16.0.jar;%APP_HOME%\lib\rhino-1.7.10.jar;%APP_HOME%\lib\jrubyparser-0.5.3.jar;%APP_HOME%\lib\javaparser-symbol-solver-logic-3.13.1.jar;%APP_HOME%\lib\javaparser-symbol-solver-model-3.13.1.jar;%APP_HOME%\lib\guava-27.0-jre.jar;%APP_HOME%\lib\commons-codec-1.10.jar;%APP_HOME%\lib\ph-commons-9.3.0.jar;%APP_HOME%\lib\slf4j-api-1.7.25.jar;%APP_HOME%\lib\jetty-webapp-9.4.6.v20170531.jar;%APP_HOME%\lib\websocket-server-9.4.6.v20170531.jar;%APP_HOME%\lib\jetty-servlet-9.4.6.v20170531.jar;%APP_HOME%\lib\jetty-security-9.4.6.v20170531.jar;%APP_HOME%\lib\jetty-server-9.4.6.v20170531.jar;%APP_HOME%\lib\websocket-servlet-9.4.6.v20170531.jar;%APP_HOME%\lib\junit-4.8.2.jar;%APP_HOME%\lib\commons-lang3-3.1.jar;%APP_HOME%\lib\commons-io-2.0.1.jar;%APP_HOME%\lib\spring-webmvc-4.1.6.RELEASE.jar;%APP_HOME%\lib\jtidy-r938.jar;%APP_HOME%\lib\guice-3.0.jar;%APP_HOME%\lib\javax.inject-1.jar;%APP_HOME%\lib\ST4-4.0.8.jar;%APP_HOME%\lib\antlr-runtime-3.5.2.jar;%APP_HOME%\lib\javassist-3.24.0-GA.jar;%APP_HOME%\lib\org.eclipse.core.resources-3.13.700.jar;%APP_HOME%\lib\org.eclipse.text-3.10.100.jar;%APP_HOME%\lib\org.eclipse.core.expressions-3.6.700.jar;%APP_HOME%\lib\org.eclipse.core.runtime-3.17.100.jar;%APP_HOME%\lib\org.eclipse.core.filesystem-1.7.700.jar;%APP_HOME%\lib\javax.servlet-api-3.1.0.jar;%APP_HOME%\lib\websocket-client-9.4.6.v20170531.jar;%APP_HOME%\lib\jetty-client-9.4.6.v20170531.jar;%APP_HOME%\lib\jetty-http-9.4.6.v20170531.jar;%APP_HOME%\lib\websocket-common-9.4.6.v20170531.jar;%APP_HOME%\lib\jetty-io-9.4.6.v20170531.jar;%APP_HOME%\lib\jetty-xml-9.4.6.v20170531.jar;%APP_HOME%\lib\websocket-api-9.4.6.v20170531.jar;%APP_HOME%\lib\spring-web-4.1.6.RELEASE.jar;%APP_HOME%\lib\spring-context-4.1.6.RELEASE.jar;%APP_HOME%\lib\spring-aop-4.1.6.RELEASE.jar;%APP_HOME%\lib\spring-beans-4.1.6.RELEASE.jar;%APP_HOME%\lib\spring-expression-4.1.6.RELEASE.jar;%APP_HOME%\lib\spring-core-4.1.6.RELEASE.jar;%APP_HOME%\lib\aopalliance-1.0.jar;%APP_HOME%\lib\cglib-2.2.1-v20090111.jar;%APP_HOME%\lib\jsr305-3.0.2.jar;%APP_HOME%\lib\failureaccess-1.0.jar;%APP_HOME%\lib\listenablefuture-9999.0-empty-to-avoid-conflict-with-guava.jar;%APP_HOME%\lib\checker-qual-2.5.2.jar;%APP_HOME%\lib\error_prone_annotations-2.2.0.jar;%APP_HOME%\lib\j2objc-annotations-1.1.jar;%APP_HOME%\lib\animal-sniffer-annotations-1.17.jar;%APP_HOME%\lib\javaparser-core-3.13.1.jar;%APP_HOME%\lib\org.eclipse.osgi-3.15.200.jar;%APP_HOME%\lib\org.eclipse.core.jobs-3.10.700.jar;%APP_HOME%\lib\org.eclipse.core.contenttype-3.7.600.jar;%APP_HOME%\lib\org.eclipse.equinox.app-1.4.400.jar;%APP_HOME%\lib\org.eclipse.equinox.registry-3.8.700.jar;%APP_HOME%\lib\org.eclipse.equinox.preferences-3.7.700.jar;%APP_HOME%\lib\org.eclipse.core.commands-3.9.700.jar;%APP_HOME%\lib\org.eclipse.equinox.common-3.11.0.jar;%APP_HOME%\lib\jetty-util-9.4.6.v20170531.jar;%APP_HOME%\lib\commons-logging-1.2.jar;%APP_HOME%\lib\asm-3.1.jar

@rem Execute gumtree
"%JAVA_EXE%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %GUMTREE_OPTS%  -classpath "%CLASSPATH%" com.github.gumtreediff.client.Run %CMD_LINE_ARGS%

:end
@rem End local scope for the variables with windows NT shell
if "%ERRORLEVEL%"=="0" goto mainEnd

:fail
rem Set variable GUMTREE_EXIT_CONSOLE if you need the _script_ return code instead of
rem the _cmd.exe /c_ return code!
if  not "" == "%GUMTREE_EXIT_CONSOLE%" exit 1
exit /b 1

:mainEnd
if "%OS%"=="Windows_NT" endlocal

:omega
