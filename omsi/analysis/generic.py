"""
Generic analysis class used to represent analyses of unknown type, e.g., when loading
a custom user-defined analysis from file for which the indicate class may not be
available with the local installation. In this case we want to at least be able
to load and investigate the data.
"""
from omsi.analysis.base import analysis_base
from omsi.analysis.analysis_data import analysis_dtypes
from omsi.shared.dependency_data import dependency_dict
from omsi.shared.log import log_helper
import pickle
try:
    import cloudpickle   # Use the version of cloud-pickle installed on the system
    log_helper.debug(__name__, "Using system cloudpickle module")
except ImportError:
    try:
        import omsi.shared.third_party.cloudpickle as cloudpickle
        log_helper.debug(__name__, "Using fallback cloudpickle version")
    except ImportError:
        log_helper.warning(__name__, "cloudpickle could not be imported. Using standard pickle instead. " +
                           " Some features may not be available.")
        import pickle as cloudpickle
import numpy as np


class analysis_generic(analysis_base):
    """
    This analysis class is used if the specific anlaysis type is unknown, e.g., when loading
    custom user-defined analysis data that may have not be available in the standard
    omsi package used.
    """
    DEFAULT_OUTPUT_PREFIX = "output_"

    @classmethod
    def from_function(cls, analysis_function, output_names=None):
        """
        Create a generic analysis class for a given analysis function.

        This functionality is useful to ease quick scripting on analyses but should not be used in production

        :param analysis_function: The analysis function to be wrapped for provenance tracking and storage
        :param output_names: Optionally, define a list of the names of the outputs

        :return: A new generic analysis class
        """
        log_helper.debug(__name__, "Creating generic analysis from function")
        generic_analysis = cls()
        for var in analysis_function.__code__.co_varnames:
            generic_analysis.add_parameter(name=var, help='')
        generic_analysis.add_parameter(name='__analysis_function',
                                       help='The analysis function we want to execute',
                                       dtype=str)
        if output_names is not None:
            generic_analysis.data_names = output_names
        generic_analysis['__analysis_function'] = cloudpickle.dumps(analysis_function)
        return generic_analysis

    def __init__(self, name_key="undefined"):
        """
        Initialize the basic data members

        :param name_key: The name for the analysis
        """
        super(analysis_generic, self).__init__()
        self.analysis_identifier = name_key
        self.real_analysis_type = None  # This is the analysis type indicated in the HDF5 file

    def __getitem__(self,
                    key):
        """
        Overwrite the __getitem__ behavior to allow the use of a wrapped function
        analysis as part of a regular workflow when the outputs are not known yet
        """
        re = super(analysis_generic, self).__getitem__(key)
        if re is None:
            if isinstance(key, basestring) and key.startswith(self.DEFAULT_OUTPUT_PREFIX):
                re = dependency_dict(param_name=None,
                                     link_name=None,
                                     dataname=key,
                                     omsi_object=self,
                                     selection=None,
                                     help=None)
        return re

    def execute(self, **kwargs):
        # Update the dtype of all the input parameters to ensure we save them correctly to file
        log_helper.debug(__name__, "Setting parameters based on the given inputs")
        ana_dtypes = analysis_dtypes.get_dtypes()
        for k, v in kwargs.iteritems():
            for p in self.parameters:
                if p['name'] == k:
                    if hasattr(v, 'dtype'):
                        p['dtype'] = ana_dtypes['ndarray']
                    else:
                        p['dtype'] = type(v)
        # Execute the analysis as usual
        result = super(analysis_generic, self).execute(**kwargs)
        return result

    def execute_analysis(self):
        """
        Nothing to do here.
        """
        if self['__analysis_function'] is not None:
            log_helper.debug(__name__, "Compiling the input dict for the analysis function.")
            input_dict = {}
            for arg in self.parameters:
                if arg['data'] is not None and arg['name'] != '__analysis_function':
                    input_dict[arg['name']] = arg['data']
            # When we restored the analysis we did not know that the parameter was supposed to be unicode
            log_helper.debug(__name__, "Unpickel the analysis function")
            if isinstance(self['__analysis_function'], np.ndarray):
                self['__analysis_function'] = self['__analysis_function'][0]
            analysis_function = self['__analysis_function']
            analysis_function = pickle.loads(analysis_function)
            log_helper.debug(__name__, "Executing the analysis function")
            result = analysis_function(**input_dict)
            log_helper.debug(__name__, "Creating output data names and returning results")
            if isinstance(result, tuple):
                if len(self.data_names) >= len(result):
                    pass
                else:
                    self.data_names = [(self.DEFAULT_OUTPUT_PREFIX + str(i))
                                       for i in range(len(self.data_names), len(result))]
            elif result is None:
                self.data_names = []
            else:
                self.data_names = [self.DEFAULT_OUTPUT_PREFIX + '0']
            return result
        else:
            raise NotImplementedError("We cannot run this analysis. Analysis_generic cannot run " +
                                      "an analysis unless an analysis function is set.")

    @classmethod
    def v_qslice(cls,
                 analysis_object,
                 z,
                 viewer_option=0):
        """
        Implement support for qslice URL requests for the viewer
        """
        return super(analysis_generic, cls).v_qslice(analysis_object, z, viewer_option)

    @classmethod
    def v_qspectrum(cls,
                    analysis_object,
                    x,
                    y,
                    viewer_option=0):
        """
        Implement support for qspectrum URL requests for the viewer
        """
        return super(analysis_generic, cls).v_qspectrum(analysis_object, x, y, viewer_option)

    @classmethod
    def v_qmz(cls,
              analysis_object,
              qslice_viewer_option=0,
              qspectrum_viewer_option=0):
        """
        Implement support for qmz URL requests for the viewer
        """
        return super(analysis_generic, cls).v_qmz(analysis_object, qslice_viewer_option, qspectrum_viewer_option)

    @classmethod
    def v_qspectrum_viewer_options(cls,
                                   analysis_object):
        """
        Define which viewer_options are supported for qspectrum URL's
        """
        return super(analysis_generic, cls).v_qspectrum_viewer_options(analysis_object)

    @classmethod
    def v_qslice_viewer_options(cls,
                                analysis_object):
        """
        Define which viewer_options are supported for qspectrum URL's
        """
        return super(analysis_generic, cls).v_qslice_viewer_options(analysis_object)

    @classmethod
    def get_analysis_type(cls):
        """
        Return a string indicating the type of analysis performed
        """
        return "generic"

    def read_from_omsi_file(self,
                            analysis_object,
                            load_data=True,
                            load_parameters=True,
                            load_runtime_data=True,
                            dependencies_omsi_format=True,
                            ignore_type_conflict=False):
        """
        See `omsi.analysis.analysis_base.read_from_omsi_file(...)` for details.
        The function is overwritten here mainly to initialize the self.real_analysis_type
        instance variable but otherwise uses the default behavior.

        """
        # Attempt to add all analysis parameters to avoid warnings when setting the parameters during
        # the data load process, when we would set parameters that are not defined yet
        try:
            parameter_list = analysis_object.get_all_parameter_data(load_data=False,
                                                                    exclude_dependencies=False)
            for param in parameter_list:
                self.add_parameter(name=param['name'],
                                   help=param['help'],
                                   dtype=param['dtype'])
        except:
            log_helper.warning(__name__, "Could not generate all parameters.")
        # Load the data as usual
        output_val = super(analysis_generic, self).read_from_omsi_file(
            analysis_object=analysis_object,
            load_data=load_data,
            load_parameters=load_parameters,
            load_runtime_data=load_runtime_data,
            dependencies_omsi_format=dependencies_omsi_format,
            ignore_type_conflict=ignore_type_conflict)
        # Load the real data type.
        self.real_analysis_type = unicode(analysis_object.get_analysis_type()[:])
        # Return the output data
        return output_val

    def get_real_analysis_type(self):
        """
        This class is designed to handle generic (including unkown) types of analysis.
        In cases, e.g., were this class is used to store analysis data from an HDF5
        file we may have an actual analysis type available even if we do not have
        a special analysis class may not be available in the current installation
        """
        return self.real_analysis_type

