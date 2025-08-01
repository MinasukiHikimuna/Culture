@echo off
REM Reddit Data Extraction Batch Script
REM This script helps you run the Reddit extractor with proper environment setup

echo ============================================
echo Reddit Data Extractor for GWASI Data  
echo ============================================
echo.

REM Check if environment variables are set
if "%REDDIT_CLIENT_ID%"=="" (
    echo ERROR: REDDIT_CLIENT_ID environment variable not set
    echo Please set up your Reddit API credentials first.
    echo See REDDIT_SETUP.md for instructions.
    echo.
    pause
    exit /b 1
)

if "%REDDIT_CLIENT_SECRET%"=="" (
    echo ERROR: REDDIT_CLIENT_SECRET environment variable not set  
    echo Please set up your Reddit API credentials first.
    echo See REDDIT_SETUP.md for instructions.
    echo.
    pause
    exit /b 1
)

echo Environment variables configured correctly.
echo.

REM Find the most recent gwasi data file
echo Looking for gwasi data files...
for /f "delims=" %%f in ('dir /b /o:-d extracted_data\gwasi_data_*.csv 2^>nul') do (
    set LATEST_FILE=extracted_data\%%f
    goto :found
)

echo ERROR: No gwasi data files found in extracted_data directory.
echo Please run gwasi_extractor.py first to generate data.
echo.
pause
exit /b 1

:found
echo Found latest gwasi data file: %LATEST_FILE%
echo.

REM Ask user for options
set /p MAX_POSTS="Enter max posts to process (leave blank for all): "
set /p OUTPUT_DIR="Enter output directory (leave blank for 'reddit_data'): "

if "%OUTPUT_DIR%"=="" set OUTPUT_DIR=reddit_data
if "%MAX_POSTS%"=="" (
    set MAX_POSTS_ARG=
) else (
    set MAX_POSTS_ARG=--max-posts %MAX_POSTS%
)

echo.
echo Starting Reddit data extraction...
echo Input file: %LATEST_FILE%
echo Output directory: %OUTPUT_DIR%
if not "%MAX_POSTS%"=="" echo Max posts: %MAX_POSTS%
echo.

REM Run the extraction
python reddit_extractor.py "%LATEST_FILE%" --output "%OUTPUT_DIR%" %MAX_POSTS_ARG%

echo.
echo ============================================
echo Extraction completed. Check the output directory for results.
pause