from azos.conf.laconfig_parser import LaconfigParser


def test_parse_simple_config():
    source = """
    app
    {
      log-level = debug
      database
      {
        connection = \"mongo://localhost\"
      }
    }
    """
    config = LaconfigParser(source).parse()
    root = config.root
    assert root.name == "app"
    assert root.attr_by_name("log-level").value == "debug"
    assert root.get_child("database").attr_by_name("connection").value == "mongo://localhost"


def test_parse_section_with_value():
    source = """
    root
    {
      logger = file
      {
        path = \"c:\\\\logs\"
      }
    }
    """
    config = LaconfigParser(source).parse()
    root = config.root
    logger = root.get_child("logger")
    assert logger.value == "file"
    assert logger.attr_by_name("path").value == "c:\\logs"
