"""A small, hand-kept vocabulary of skills and domains.

People describe themselves in their own words ("healthcare", "pyhton", "web
dev"), and organizations tag themselves in theirs ("medical imaging", "c/c++",
"heathcare"). Matching words to words misses most of that. Each concept here
has the spellings that mean it, the broader concept it belongs to, and a few
related ones, so `healthcare` finds an organization tagged `radiology` and
`react` counts as JavaScript.

Short or common words that are also English words (`go`, `c`, `r`, `react`,
`spring`) are only trusted in tags and in what a person types, never in free
text such as a description, unless they appear with their usual capital
letter ("Go", "React").
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from functools import lru_cache

SKILL = "skill"
DOMAIN = "domain"


@dataclass(frozen=True)
class Concept:
    key: str
    kind: str
    label: str
    terms: tuple[str, ...]
    broader: tuple[str, ...] = ()
    related: tuple[str, ...] = ()
    # Terms that are trusted only in tags and in what a person types.
    tag_only: tuple[str, ...] = ()
    # Terms trusted in free text only with this exact capitalisation.
    cased: tuple[str, ...] = field(default=())


def _c(
    key: str,
    kind: str,
    terms: str = "",
    *,
    label: str = "",
    broader: str = "",
    related: str = "",
    tag_only: str = "",
    cased: str = "",
) -> Concept:
    def split(value: str) -> tuple[str, ...]:
        return tuple(t.strip() for t in value.split("|") if t.strip())

    return Concept(
        key=key,
        kind=kind,
        label=label or key,
        terms=tuple(dict.fromkeys([key, *split(terms)])),
        broader=split(broader),
        related=split(related),
        tag_only=split(tag_only),
        cased=split(cased),
    )


# fmt: off
_SKILLS = [
    # Languages
    _c("python", SKILL, "python3|python 3|py|cpython|phyton|pyhton|pyton|pythn|python programming", label="Python", tag_only="py"),
    _c("javascript", SKILL, "js|javascipt|java script|ecmascript|es6|vanilla js", label="JavaScript", tag_only="js"),
    _c("typescript", SKILL, "ts|typescipt", label="TypeScript", broader="javascript", tag_only="ts"),
    _c("java", SKILL, "jvm|jdk|java se|java ee|jakartaee|jakarta ee|javafx|eclipsejavaide", label="Java"),
    _c("kotlin", SKILL, "kotlin multiplatform|kmp", label="Kotlin", related="java|android"),
    _c("c", SKILL, "c language|ansi c|c99|c11|c programming", label="C", related="c++", tag_only="c"),
    _c("c++", SKILL, "cpp|cplusplus|c plus plus|c++17|c++20|modern c++", label="C++", related="c"),
    _c("c#", SKILL, "csharp|c sharp|.net|dotnet|asp.net", label="C#"),
    _c("go", SKILL, "golang|go language", label="Go", tag_only="go", cased="Go"),
    _c("rust", SKILL, "rustlang|rust language", label="Rust", cased="Rust"),
    _c("ruby", SKILL, "rubygems", label="Ruby"),
    _c("php", SKILL, "symfony|laravel|composer php", label="PHP"),
    _c("swift", SKILL, "swiftui", label="Swift", related="ios", tag_only="swift", cased="Swift"),
    _c("objective-c", SKILL, "objective c|objc", label="Objective-C"),
    _c("dart", SKILL, "", label="Dart", tag_only="dart", cased="Dart"),
    _c("r", SKILL, "r language|r-project|rlang|r programming|cran|rstats|shiny|tidyverse", label="R", related="statistics", tag_only="r"),
    _c("julia", SKILL, "julialang|julia language", label="Julia", cased="Julia"),
    _c("haskell", SKILL, "ghc|cabal", label="Haskell", broader="functional programming"),
    _c("scala", SKILL, "", label="Scala", related="java"),
    _c("ocaml", SKILL, "", label="OCaml", broader="functional programming"),
    _c("elixir", SKILL, "erlang|beam vm|otp", label="Elixir/Erlang", broader="functional programming"),
    _c("clojure", SKILL, "lisp|scheme|racket|common lisp", label="Lisp", broader="functional programming", tag_only="scheme"),
    _c("lua", SKILL, "luajit|luarocks", label="Lua"),
    _c("perl", SKILL, "raku", label="Perl"),
    _c("fortran", SKILL, "", label="Fortran", related="scientific computing"),
    _c("assembly", SKILL, "asm|assembly language|x86 assembly|arm assembly|fasm|nasm", label="Assembly", related="c|operating systems", tag_only="assembly"),
    _c("shell", SKILL, "bash|shell script|shell scripting|posix shell|zsh|sh", label="Shell", tag_only="sh"),
    _c("sql", SKILL, "plsql|t-sql|sqlite", label="SQL", related="databases"),
    _c("matlab", SKILL, "octave", label="MATLAB", related="scientific computing"),
    _c("zig", SKILL, "", label="Zig", related="c|systems programming"),
    _c("d", SKILL, "dlang", label="D", tag_only="d"),
    _c("smalltalk", SKILL, "pharo|squeak", label="Smalltalk"),
    _c("solidity", SKILL, "", label="Solidity", related="blockchain"),
    _c("html", SKILL, "html5|xhtml", label="HTML", related="css|web"),
    _c("css", SKILL, "css3|scss|sass|less css|tailwind|tailwindcss|bootstrap", label="CSS", related="html|frontend", tag_only="bootstrap"),
    _c("webassembly", SKILL, "wasm|web assembly", label="WebAssembly", related="rust|c++|web"),
    _c("cuda", SKILL, "opencl|gpu programming|gpgpu|hip|sycl", label="GPU programming", related="c++|high-performance computing", tag_only="hip"),
    _c("verilog", SKILL, "vhdl|systemverilog|hdl|chisel", label="Hardware description languages", related="embedded", tag_only="chisel"),
    _c("tcl", SKILL, "tcl/tk", label="Tcl"),
    # JavaScript frameworks and runtimes
    _c("react", SKILL, "reactjs|react.js|react js|react hooks|reactjs javascript", label="React", broader="javascript|frontend", tag_only="react", cased="React"),
    _c("react native", SKILL, "react-native", label="React Native", broader="javascript|mobile"),
    _c("vue", SKILL, "vue.js|vuejs|vue 3|nuxt", label="Vue", broader="javascript|frontend"),
    _c("angular", SKILL, "angularjs|angular.js", label="Angular", broader="typescript|frontend", tag_only="angular"),
    _c("svelte", SKILL, "sveltekit", label="Svelte", broader="javascript|frontend"),
    _c("next.js", SKILL, "nextjs|next js", label="Next.js", broader="react|web"),
    _c("nodejs", SKILL, "node|node.js|node js|express|expressjs|nestjs|deno|bun", label="Node.js", broader="javascript|backend", tag_only="node|express|bun"),
    _c("electron", SKILL, "", label="Electron", broader="javascript|desktop", tag_only="electron"),
    _c("jquery", SKILL, "", label="jQuery", broader="javascript"),
    _c("canvas", SKILL, "html canvas|p5.js|three.js|threejs|webgl|webgpu|d3|d3.js", label="Browser graphics (WebGL, canvas, D3)", broader="javascript", related="graphics|data visualization", tag_only="canvas|d3"),
    # Python libraries and frameworks
    _c("django", SKILL, "django rest framework|drf|django+postgresql", label="Django", broader="python|backend"),
    _c("flask", SKILL, "fastapi|starlette|tornado|zope|pyramid", label="Flask/FastAPI", broader="python|backend", tag_only="tornado|pyramid"),
    _c("numpy", SKILL, "scipy|numba|cython|xarray|zarr|netcdf", label="NumPy/SciPy", broader="python|scientific computing"),
    _c("pandas", SKILL, "polars|dataframes|dataframe", label="pandas", broader="python|data science", tag_only="polars"),
    _c("pytest", SKILL, "flake8|pylint|mypy|pyflakes|tox|pre-commit hooks", label="Python tooling (pytest, flake8, mypy)", broader="python"),
    _c("jupyter", SKILL, "jupyterlab|ipython|notebooks|jupyter notebooks", label="Jupyter", broader="python|data science", tag_only="notebooks"),
    _c("pytorch", SKILL, "torch|tensorflow|keras|jax|scikit-learn|sklearn|huggingface|hugging face|transformers|onnx|xgboost|machine learning (ml)", label="ML frameworks (PyTorch, TensorFlow, scikit-learn)", broader="python|machine learning", tag_only="torch"),
    _c("opencv", SKILL, "open cv", label="OpenCV", broader="computer vision"),
    _c("nltk", SKILL, "spacy|gensim|stanza|nltk python", label="NLP libraries (NLTK, spaCy)", broader="python|natural language processing"),
    _c("leaflet", SKILL, "openlayers|maplibre|mapbox|cesium|leaflet.js", label="Web map libraries (Leaflet, OpenLayers)", broader="javascript|geospatial"),
    _c("phoenix", SKILL, "phoenix framework|phoenix liveview|liveview", label="Phoenix", broader="elixir|backend", tag_only="phoenix"),
    _c("qt", SKILL, "qml|pyqt|pyside|qt5|qt6", label="Qt", broader="c++|desktop"),
    _c("gtk", SKILL, "gtkmm|gtk4|gtk3|gobject|glib|libadwaita", label="GTK", broader="c|desktop"),
    _c("wxwidgets", SKILL, "", label="wxWidgets", broader="c++|desktop"),
    # Other frameworks and platforms
    _c("rails", SKILL, "ruby on rails|ror", label="Ruby on Rails", broader="ruby|backend", tag_only="rails", cased="Rails"),
    _c("spring", SKILL, "spring boot|springboot|spring framework", label="Spring", broader="java|backend", tag_only="spring", cased="Spring Boot"),
    _c("android", SKILL, "android sdk|android studio|jetpack compose|android development", label="Android", broader="mobile", related="kotlin|java"),
    _c("ios", SKILL, "iphone|ipad|xcode", label="iOS", broader="mobile", related="swift"),
    _c("flutter", SKILL, "dart/flutter|flutter app", label="Flutter", broader="dart|mobile"),
    _c("unity", SKILL, "unreal|unreal engine|godot|bevy", label="Game engines", broader="games", tag_only="unity", cased="Unity"),
    _c("opengl", SKILL, "vulkan|directx|metal api|glsl|shaders|opengl es", label="OpenGL/Vulkan", broader="graphics"),
    _c("llvm", SKILL, "mlir|clang|gcc|lld|lldb|gnu toolchain", label="LLVM/GCC", broader="compilers"),
    _c("ros", SKILL, "ros2|ros 2|robot operating system|gazebo|moveit", label="ROS", broader="robotics"),
    _c("kubernetes", SKILL, "k8s|helm|kubectl|operators|kubevirt|kubeflow", label="Kubernetes", broader="cloud native", tag_only="helm|operators"),
    _c("docker", SKILL, "containers|container|podman|containerd|dockerfile|oci", label="Docker/containers", broader="devops", tag_only="container|oci"),
    _c("terraform", SKILL, "ansible|puppet|chef|infrastructure as code|iac", label="Infrastructure as code", broader="devops", tag_only="chef"),
    _c("git", SKILL, "github|gitlab|version control|mercurial|hg", label="Git", related="developer tools", tag_only="hg"),
    _c("github actions", SKILL, "github-actions|gitlab ci|jenkins|ci pipelines", label="CI pipelines", broader="devops"),
    _c("postgresql", SKILL, "postgres|psql|postgis", label="PostgreSQL", broader="databases|sql"),
    _c("mysql", SKILL, "mariadb", label="MySQL/MariaDB", broader="databases|sql"),
    _c("mongodb", SKILL, "couchdb|nosql|redis|cassandra|elasticsearch|opensearch", label="NoSQL databases", broader="databases"),
    _c("spark", SKILL, "apache spark|hadoop|apache beam|flink|kafka|airflow|dask", label="Data processing (Spark, Kafka, Dask)", broader="big data", tag_only="spark"),
    _c("graphql", SKILL, "rest api|rest apis|openapi|grpc|protobuf", label="APIs (REST, GraphQL, gRPC)", broader="backend"),
    _c("linux", SKILL, "gnu/linux|unix|posix|bsd", label="Linux/Unix", related="operating systems"),
    _c("ebpf", SKILL, "bpf|kvm|xen|qemu|hypervisor", label="Kernel and virtualization tools", broader="operating systems"),
    _c("micropython", SKILL, "circuitpython|arduino|esp32|raspberry pi|stm32|pixhawk|rtos|freertos|zephyr", label="Microcontrollers", broader="embedded"),
    _c("latex", SKILL, "tex|markdown|restructuredtext|sphinx|docusaurus|mkdocs", label="Docs tooling (LaTeX, Markdown, Sphinx)", broader="documentation", tag_only="tex|markdown"),
    _c("blender", SKILL, "", label="Blender", broader="graphics"),
    _c("webrtc", SKILL, "", label="WebRTC", broader="communication", related="video"),
]

_DOMAINS = [
    # Artificial intelligence and data
    _c("machine learning", DOMAIN, "ml|machine-learning|deep learning|neural networks|neural network|ai/ml|ml/ai|artificial intelligence|artificial-intelligence|ai|reinforcement learning|data mining|predictive modeling|scientific machine learning", label="Machine learning and AI"),
    _c("large language models", DOMAIN, "llm|llms|generative ai|genai|gen ai|chatbots|chatbot|rag|retrieval augmented generation|ai agents|agents|agentic|software agent|mcp|a2a|prompt engineering|language models|foundation models", label="LLMs and AI agents", broader="machine learning", related="natural language processing", tag_only="agents|mcp|a2a|rag"),
    _c("computer vision", DOMAIN, "image recognition|image classification|object detection|image processing|image analysis|image segmentation|segmentation|video analysis|ocr|optical character recognition|handwriting recognition|text recognition|pose estimation|camera pipeline|camera pipelines|image pipeline|image pipelines|camera|cameras|vision", label="Computer vision", broader="machine learning", related="graphics|medical imaging", tag_only="vision|segmentation|camera|cameras"),
    _c("natural language processing", DOMAIN, "nlp|text mining|speech recognition|speech|machine translation|text processing|computational linguistics|language technology", label="Natural language processing", broader="machine learning", related="languages and linguistics"),
    _c("data science", DOMAIN, "data|data analysis|data analytics|analytics|data-science|exploratory data analysis|business intelligence", label="Data science", related="statistics|machine learning|data visualization", tag_only="data"),
    _c("statistics", DOMAIN, "statistical computing|statistical|biostatistics|econometrics|bayesian|probabilistic programming", label="Statistics", related="data science|mathematics"),
    _c("data visualization", DOMAIN, "data viz|data vis|visualization|visualisation|data visualisation|dataviz|plotting|charts|dashboards|scientific visualization|visual analytics", label="Data visualization", related="data science"),
    _c("big data", DOMAIN, "data engineering|data pipelines|etl|stream processing|distributed data|data processing|data lakes|data warehouse", label="Data engineering and big data", related="databases|cloud native", tag_only="data processing"),
    _c("databases", DOMAIN, "database|dbms|data storage|query engine|query optimization|storage engines|database systems|sql databases|data management", label="Databases", related="big data"),
    _c("open data", DOMAIN, "linked data|semantic web|knowledge graph|knowledge graphs|rdf|sparql|ontologies|ontology|wikidata|open knowledge|open access|metadata|data standards|open standards", label="Open data and knowledge graphs", related="digital humanities|science", tag_only="metadata"),
    # Science and health
    _c("science", DOMAIN, "science and medicine|open science|scientific software|research software|citizen science|research", label="Science and research software", tag_only="research|science"),
    _c("scientific computing", DOMAIN, "numerical computation|numerical computing|numerical methods|numerical analysis|computational science|simulation|simulations|modelling|modeling|solvers|finite element|differential equations|scientific python", label="Scientific computing", broader="science", related="mathematics|high-performance computing|physics", tag_only="modelling|modeling"),
    _c("high-performance computing", DOMAIN, "hpc|parallel computing|supercomputing|mpi|openmp|performance optimisation|performance optimization|simd|distributed computing", label="High-performance computing", related="scientific computing|systems programming", tag_only="performance optimisation|performance optimization"),
    _c("mathematics", DOMAIN, "math|maths|algebra|computer algebra|symbolic math|symbolic computation|geometry|computational geometry|number theory|game theory|combinatorics|theorem proving|formal verification|optimization|linear algebra|calculus", label="Mathematics", broader="science", related="scientific computing|statistics", tag_only="optimization"),
    _c("physics", DOMAIN, "particle physics|high energy physics|hep|nuclear physics|plasma physics|fluid dynamics|cfd|computational physics", label="Physics", broader="science", related="astronomy|scientific computing"),
    _c("quantum computing", DOMAIN, "quantum|qiskit|quantum circuits|quantum software", label="Quantum computing", broader="science", related="physics"),
    _c("astronomy", DOMAIN, "astrophysics|space|space science|telescope|telescopes|cosmology|solar physics|planetary science|astroinformatics|satellites|satellite|spacecraft|heliophysics|gravitational waves|radio astronomy", label="Astronomy and space", broader="science", related="physics", tag_only="space"),
    _c("bioinformatics", DOMAIN, "genomics|computational biology|genetics|sequencing|genome|genomes|dna|rna|proteins|protein|proteomics|systems biology|network biology|molecular biology|single-cell|variant calling|phylogenetics|structural biology", label="Bioinformatics and genomics", broader="biology", related="health|chemistry"),
    _c("biology", DOMAIN, "biological|life sciences|ecology|biodiversity|microbiology|marine biology|zoology|botany|plant science|evolution", label="Biology and ecology", broader="science", related="bioinformatics|climate", tag_only="evolution"),
    _c("neuroscience", DOMAIN, "neuroinformatics|brain|eeg|fmri|neuroimaging|cognitive science|neurons", label="Neuroscience", broader="science", related="biology|health|machine learning"),
    _c("chemistry", DOMAIN, "cheminformatics|drug discovery|molecular|molecules|materials science|computational chemistry|quantum chemistry|molecular dynamics", label="Chemistry and materials", broader="science", related="biology"),
    _c("health", DOMAIN, "healthcare|heathcare|health care|medical|medicine|clinical|clinics|clinic|hospital|hospitals|patients|patient|ehr|emr|electronic health records|medical records|fhir|hl7|dicom|radiology|cancer|oncology|precision medicine|public health|global health|epidemiology|health informatics|mental health|nursing|telemedicine|pharmacy", label="Health and medicine", related="biology|medical imaging", tag_only="health"),
    _c("medical imaging", DOMAIN, "radiology imaging|medical image|medical images|pathology imaging|microscopy|ultrasound|mri|ct scans", label="Medical imaging", broader="health", related="computer vision"),
    _c("climate", DOMAIN, "climate change|environment|environmental|earth science|earth sciences|weather|meteorology|oceanography|ocean|polar science|geoscience|geosciences|hydrology|sustainability|renewable energy|energy|carbon|air quality|agriculture|forestry|disaster|natural hazards", label="Climate, environment and earth science", broader="science", related="geospatial", tag_only="environment|energy"),
    _c("geospatial", DOMAIN, "gis|geographic information systems|maps|map|mapping|web maps|cartography|openstreetmap|osm|geoinformation|geoinformatics|geography|spatial data|spatial|location|navigation|gps|remote sensing|geodata|spatial information infrastructures|google earth|geocoding|routing", label="Maps and geospatial", related="climate|open data", tag_only="osm|spatial|location|map|routing|mapping|navigation"),
    # Systems
    _c("operating systems", DOMAIN, "operating system|os|kernel|kernels|linux kernel|device drivers|drivers|bootloader|filesystems|file systems|filesystem|virtualization|unikernels|microkernel|posix|system software|bsd|init systems|kernel development", label="Operating systems and kernels", broader="systems programming", related="embedded", tag_only="os|bsd|posix|kernel|kernels|drivers"),
    _c("systems programming", DOMAIN, "systems|low-level|low level|low-level programming|performance|memory safety|concurrency|runtime|runtimes|garbage collection|garbage-collection|system programming", label="Systems programming", related="operating systems|compilers", tag_only="systems|performance|runtime|runtimes"),
    _c("embedded", DOMAIN, "embedded systems|microcontrollers|microcontroller|firmware|iot|internet of things|hardware|electronics|fpga|risc-v|arm|eda|chip design|hardware design|open hardware|sensors|real-time|realtime|real-time systems", label="Embedded systems and hardware", related="robotics|operating systems", tag_only="arm|hardware|sensors|real-time|realtime"),
    _c("compilers", DOMAIN, "compiler|programming languages|programming language|language design|interpreters|interpreter|parsers|parser|parsers & compilers|type systems|type checking|static analysis|static code analysis|program analysis|jit|code generation|toolchain|toolchains|language tooling|language server|lsp|transpiler|virtual machines|bytecode", label="Compilers and programming languages", related="systems programming|developer tools|functional programming", tag_only="parser|parsers"),
    _c("functional programming", DOMAIN, "fp|lambda calculus|type theory|purely functional", label="Functional programming", related="compilers", tag_only="fp"),
    _c("networking", DOMAIN, "network|networks|computer networks|protocols|protocol|routing protocols|routing protocol|network routing|packet routing|packet capture|packet analysis|vpn|tcp/ip|tcp/udp|sdn|software defined networking|wireless|telecom|telecommunications|5g|p2p|peer-to-peer|mesh networking|dns|network topology", label="Networking", related="cloud native|security", tag_only="network|protocol|protocols"),
    _c("cloud native", DOMAIN, "cloud|cloud computing|cloud-native|infrastructure|serverless|microservices|distributed systems|service mesh|orchestration|container orchestration|observability|monitoring|telemetry|opentelemetry|prometheus|sre|site reliability|scalability|edge computing|storage|software-defined-storage", label="Cloud and distributed systems", related="devops|networking", tag_only="storage|infrastructure|scalability"),
    _c("devops", DOMAIN, "ci/cd|ci|cd|continuous integration|continuous delivery|continuous deployment|build systems|release engineering|automation|deployment|packaging|package management|package managers|linux distributions|linux distribution|distro|distros|reproducible builds|nix|flatpak", label="DevOps, CI and packaging", related="cloud native|developer tools", tag_only="ci|cd|automation|packaging|deployment"),
    _c("security", DOMAIN, "cybersecurity|cyber security|infosec|application security|appsec|web security|fuzzing|fuzz testing|fuzz-testing|vulnerabilities|vulnerability|cryptography|crypto|encryption|privacy|penetration testing|pentesting|malware|reverse engineering|disassembly|binary analysis|threat detection|intrusion detection|authentication|identity|zero trust|ctf|secure", label="Security and privacy", related="networking|compliance", tag_only="crypto|identity|secure|authentication"),
    _c("compliance", DOMAIN, "license compliance|open source compliance|licensing|compliance automation|software licenses|legal", label="Licensing and compliance", related="security", tag_only="legal"),
    _c("developer tools", DOMAIN, "devtools|dev tools|development tools|tooling|ide|ides|code editor|code editors|editor|editors|debugger|debuggers|debugging|linters|linter|linting|code quality|code style|style checkers|formatters|testing|test automation|test frameworks|testing frameworks|unit testing|code review|code review tool|command line|command line tools|command-line|command-line tools|cli|cli tools|terminal|profilers|profiling|build tools|api clients|developer experience", label="Developer tools", related="compilers|devops", tag_only="cli|terminal|editor|editors|testing|tooling|linting|code quality|code style|style checkers"),
    # Applications
    _c("web", DOMAIN, "web development|web dev|webdev|web-development|websites|website|web apps|web app|web applications|web application|full stack|full-stack|fullstack|web platform|browser|browsers|web services", label="Web development"),
    _c("frontend", DOMAIN, "frontends|front-end|front end|frontend development|user interface|user interfaces|ui|ui development|ux|user experience|ui/ux|web design|interaction design|design systems|responsive design", label="Frontend and user interfaces", broader="web", related="design"),
    _c("supply chain security", DOMAIN, "software supply chain|software supply chain security|supplychain|sbom|sboms|software bill of materials|software composition analysis|slsa|sigstore|code signing|artifact signing|build provenance|provenance|attestations|reproducible builds|dependency scanning", label="Software supply chain security", broader="security", related="devops|compliance", tag_only="supply chain|provenance"),
    _c("backend", DOMAIN, "backends|web backends|back-end|back end|server-side|server side|apis|api|rest|web apis|api design|api development|servers|server", label="Backend and APIs", broader="web", related="databases|cloud native", tag_only="api|rest|server|servers"),
    _c("content management", DOMAIN, "cms|content management systems|content management system|wordpress|drupal|joomla|blogging|publishing|website builder|static site generators", label="Content management and publishing", broader="web", tag_only="publishing"),
    _c("accessibility", DOMAIN, "a11y|screen reader|screen readers|assistive technology|assistive technologies|inclusive design|wcag|aria|disabilities|disability", label="Accessibility", related="frontend", tag_only="aria"),
    _c("design", DOMAIN, "ui design|ux design|visual design|graphic design|usability|usability research|user research|human-computer interaction|hci|prototyping|figma", label="Design and usability", related="frontend", tag_only="design"),
    _c("mobile", DOMAIN, "mobile apps|mobile app|mobile development|mobile applications|smartphones|apps|app development|cross-platform", label="Mobile apps", tag_only="apps|cross-platform"),
    _c("desktop", DOMAIN, "desktop applications|desktop apps|desktop environment|gui|guis|gnome|kde|linux desktop|window manager", label="Desktop applications", related="frontend"),
    _c("graphics", DOMAIN, "computer graphics|3d|3d graphics|2d|2d/3d graphics|rendering|renderer|ray tracing|path tracing|animation|cad|mesh processing|geometry processing|vr|ar|xr|virtual reality|augmented reality|gltf|3d modeling|3d printing|vector graphics|image editing|photo editing|raster graphics|svg|fonts|typography", label="Graphics and 3D", related="computer vision", tag_only="2d|ar|cad|rendering"),
    _c("games", DOMAIN, "game|gaming|modding|game modding|mods|game moding|game development|gamedev|game dev|game engines|game engine|video games|game design|educational games|serious games|interactive fiction", label="Games", tag_only="game"),
    _c("signal processing", DOMAIN, "dsp|digital signal processing|software defined radio|software-defined radio|sdr|radio|gnu radio|filters|communications engineering", label="Signal processing and radio", related="audio|networking|physics", tag_only="radio|filters|sdr"),
    _c("audio", DOMAIN, "music|sound|audio processing|digital audio|daw|synthesizers|synthesizer|midi|music production|music information retrieval|audio plugins|speech synthesis|podcasts", label="Music and audio", related="video"),
    _c("video", DOMAIN, "multimedia|media|streaming|video streaming|video processing|video editing|codecs|codec|subtitles|captions|ffmpeg|media players|broadcast|live streaming|video conferencing", label="Video and multimedia", related="audio|graphics|communication"),
    _c("communication", DOMAIN, "chat|realtime chat|real-time chat|chat apps|messaging|instant messaging|team chat|email|mail|mailing list|mailing lists|social|social media|social networking|social networks|fediverse|activitypub|forums|forum|collaboration|real-time communication|web real-time communication|community", label="Communication and social", related="video", tag_only="social|community|mail|collaboration|mailing list|mailing lists"),
    _c("education", DOMAIN, "edtech|ed tech|learning|teaching|e-learning|elearning|learning management|students|student|school|schools|classroom|kids|children|mooc|educational|tutoring|courses|curriculum|literacy|stem education", label="Education", tag_only="learning|students|student|courses|teaching"),
    _c("digital humanities", DOMAIN, "humanities|history|archives|archival|archiving|web archiving|libraries and archives|museums|cultural heritage|digital libraries|digital preservation|books|ebooks|wikipedia|encyclopedia|offline access|offline", label="Libraries, archives and digital humanities", related="open data", tag_only="history|books|offline"),
    _c("languages and linguistics", DOMAIN, "linguistics|translation|localization|localisation|internationalization|i18n|l10n|low-resource languages|indigenous languages|dictionaries|dictionary|language learning", label="Languages and translation", related="natural language processing|education", tag_only="dictionary|localization"),
    _c("documentation", DOMAIN, "docs|technical writing|tech writing|writing|tutorials|documentation sites|api documentation", label="Documentation and technical writing", tag_only="docs|writing|tutorials|documentation"),
    _c("finance", DOMAIN, "fintech|banking|payments|microfinance|financial inclusion|accounting|economics|financial|insurance|digital public goods", label="Finance and fintech", related="blockchain"),
    _c("blockchain", DOMAIN, "web3|cryptocurrency|smart contracts|decentralized|decentralised|distributed ledger|bitcoin|ethereum", label="Blockchain and web3"),
    _c("civic tech", DOMAIN, "government|e-government|civic|humanitarian|social good|nonprofit|non-profit|ngo|ngos|elections|democracy|transparency|legal technology|legal tech|contract management|document assembly|public sector|crisis response|human rights", label="Civic tech and social good", related="open data|finance", tag_only="transparency"),
    _c("transport", DOMAIN, "transportation|transit|public transport|public transit|automotive|vehicles|vehicle|mobility|traffic|software defined vehicles|softwaredefinedvehicles|aviation|railway", label="Transport and vehicles", related="robotics|geospatial", tag_only="vehicle|vehicles|traffic"),
    _c("robotics", DOMAIN, "robots|robot|robotic|drones|drone|uav|uavs|unmanned vehicle|unmanned vehicles|autonomous vehicles|autonomous vehicle|autonomous systems|self-driving|autopilot|embodied ai|motion planning|slam|manipulation|spatial ai", label="Robotics and drones", related="embedded|computer vision|transport", tag_only="manipulation"),
    _c("productivity", DOMAIN, "note taking|note-taking|notes|office|office suite|documents|pdf|spreadsheets|flashcards|spaced repetition|calendar|personal knowledge management|task management", label="Productivity and office tools", tag_only="notes|office|documents|calendar"),
]
# fmt: on

# The official GSoC categories are broad, so they count for little on their own.
CATEGORY_CONCEPTS: dict[str, tuple[str, ...]] = {
    "science and medicine": ("science", "health"),
    "programming languages": ("compilers",),
    "artificial intelligence": ("machine learning",),
    "development tools": ("developer tools",),
    "web": ("web",),
    "data": ("data science", "databases"),
    "infrastructure and cloud": ("cloud native", "devops"),
    "media": ("video", "audio", "graphics"),
    "operating systems": ("operating systems",),
    "security": ("security",),
    "social and communication": ("communication",),
    "end user applications": (),
    "other": (),
}

CONCEPTS: dict[str, Concept] = {c.key: c for c in [*_SKILLS, *_DOMAINS]}


def _validate() -> None:
    for concept in CONCEPTS.values():
        for ref in (*concept.broader, *concept.related):
            if ref not in CONCEPTS:
                raise ValueError(f"{concept.key} refers to unknown concept {ref}")


_validate()


@lru_cache(maxsize=1)
def _term_index() -> dict[str, tuple[str, ...]]:
    """Lowercase term -> the concepts it names (a few terms name two)."""
    index: dict[str, list[str]] = {}
    for concept in CONCEPTS.values():
        for term in concept.terms:
            index.setdefault(term.lower(), []).append(concept.key)
    return {term: tuple(keys) for term, keys in index.items()}


_BOUNDARY_BEFORE = r"(?<![\w+#.])"
_BOUNDARY_AFTER = r"(?![\w+#])"


def _alternation(terms: list[str]) -> str:
    return "|".join(re.escape(t) for t in sorted(set(terms), key=lambda t: (-len(t), t)))


@lru_cache(maxsize=2)
def _pattern(free_text: bool) -> re.Pattern[str]:
    terms: list[str] = []
    for concept in CONCEPTS.values():
        skip = {t.lower() for t in concept.tag_only} if free_text else set()
        terms.extend(t.lower() for t in concept.terms if t.lower() not in skip)
    return re.compile(_BOUNDARY_BEFORE + "(" + _alternation(terms) + ")" + _BOUNDARY_AFTER, re.I)


# A capitalised word that starts a sentence or a step as plain English: "3. Go to the
# profile screen" is not the Go language.
_PLAIN_ENGLISH_AFTER = {
    "Go": re.compile(r"\s+(?:to|back|ahead|through|into|over|out|up|down|further)\b"),
}


@lru_cache(maxsize=1)
def _cased_pattern() -> tuple[re.Pattern[str], dict[str, str]] | None:
    cased = {term: c.key for c in CONCEPTS.values() for term in c.cased}
    if not cased:
        return None
    body = _alternation(list(cased))
    return re.compile(_BOUNDARY_BEFORE + "(" + body + ")" + _BOUNDARY_AFTER), cased


# Umbrella subjects too broad to stand in for a specific interest: "web" covers
# backends and frontends alike, "science" every field.
GENERIC_PARENTS = frozenset({"science", "web"})


def find_tag_concepts(tag: str) -> dict[str, int]:
    """Concepts a tag names: any safe spelling inside it, or an ambiguous word that is
    the whole tag ("go", "performance"), but not one inside a longer tag ("systems
    management" is not systems programming)."""
    found = find_concepts(tag)
    index = _term_index()
    cleaned = re.sub(r"\s+", " ", tag.strip().lower())
    # "c/c++", "C\\C++" and "c/rust/go" are lists: each part may be a short word.
    for part in {cleaned, *(p.strip() for p in re.split(r"[/\\,]", cleaned))}:
        for key in index.get(part) or ():
            found.setdefault(key, 1)
    return found


def find_concepts(text: str, *, free_text: bool = True) -> dict[str, int]:
    """Concepts named in `text`, with how many times each appears.

    With `free_text=False` (a person's own words) every spelling counts;
    otherwise ambiguous short words need their usual capital letter.
    """
    if not text:
        return {}
    index = _term_index()
    found: dict[str, int] = {}
    for match in _pattern(free_text).finditer(text):
        for key in index.get(match.group(1).lower(), ()):
            found[key] = found.get(key, 0) + 1
    if free_text:
        cased = _cased_pattern()
        if cased is not None:
            pattern, keys = cased
            for match in pattern.finditer(text):
                plain = _PLAIN_ENGLISH_AFTER.get(match.group(1))
                if plain and plain.match(text, match.end()):
                    continue
                key = keys[match.group(1)]
                found[key] = found.get(key, 0) + 1
    return found


# Misspellings seen in GSoC tags. They match tags silently, but when a person types
# one, the correction is reported so nobody is surprised by what was searched.
KNOWN_TYPOS = frozenset(
    {"phyton", "pyhton", "pyton", "pythn", "javascipt", "typescipt", "heathcare"}
)


@dataclass(frozen=True)
class Resolved:
    """What one thing a person typed was understood as."""

    raw: str
    concepts: tuple[str, ...]
    corrected_from: str | None = None  # set when a misspelling was read as a known term


def resolve(term: str) -> Resolved:
    """Map one typed skill or interest to concepts, correcting an obvious misspelling.

    Unknown words resolve to no concept; callers then match them as plain words.
    """
    cleaned = re.sub(r"\s+", " ", term.strip().lower())
    if not cleaned:
        return Resolved(raw=term, concepts=())
    index = _term_index()
    if cleaned in index:
        fixed = label(index[cleaned][0]).lower() if cleaned in KNOWN_TYPOS else None
        return Resolved(raw=term, concepts=index[cleaned], corrected_from=fixed)
    whole = find_concepts(cleaned, free_text=False)
    if whole:
        specific = find_concepts(cleaned) if " " in cleaned else {}
        if specific or " " not in cleaned:
            return Resolved(raw=term, concepts=tuple(specific or whole))
        # Only a generic word matched ("data" in "data vizualisation"): a close spelling
        # of the whole phrase says more.
        close = difflib.get_close_matches(cleaned, list(index), n=1, cutoff=0.8)
        if close and len(close[0]) >= 4:
            return Resolved(raw=term, concepts=index[close[0]], corrected_from=close[0])
        return Resolved(raw=term, concepts=tuple(whole))
    if len(cleaned) >= 4:
        close = difflib.get_close_matches(cleaned, list(index), n=1, cutoff=0.8)
        if close and len(close[0]) >= 4:
            return Resolved(raw=term, concepts=index[close[0]], corrected_from=close[0])
    return Resolved(raw=term, concepts=())


def label(key: str) -> str:
    concept = CONCEPTS.get(key)
    return concept.label if concept else key


def broader_of(key: str) -> tuple[str, ...]:
    concept = CONCEPTS.get(key)
    return concept.broader if concept else ()


def related_of(key: str) -> tuple[str, ...]:
    concept = CONCEPTS.get(key)
    return concept.related if concept else ()


@lru_cache(maxsize=1)
def narrower_index() -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for concept in CONCEPTS.values():
        for parent in concept.broader:
            out.setdefault(parent, []).append(concept.key)
    return {k: tuple(v) for k, v in out.items()}


def kind_of(key: str) -> str | None:
    concept = CONCEPTS.get(key)
    return concept.kind if concept else None
