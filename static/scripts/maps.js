// Retrieve data passed to the script from the template
const mapsData = document.currentScript.dataset;

(async function initMap() {
  const { StreetViewService } = await google.maps.importLibrary("streetView");
  const svService = new StreetViewService();

  let coordinates = { 
    lat: parseFloat(mapsData.lat),
    lng: parseFloat(mapsData.lng),
  };
  window.coordinates = coordinates; // Used to readjust the heading

  let panoRequest = {
    location: coordinates,
    preference: google.maps.StreetViewPreference.NEAREST,
    radius: 10,
    source: google.maps.StreetViewSource.OUTDOOR
  };
  findPanorama(svService, panoRequest, coordinates);
})();

/* 
* Get the date key.
* Assumptions:
* - The panorama key is 'pano'
* - There are only 2 keys in each object
*/
function getPanoDateKey(panoArray) {
  return Object.keys(panoArray[0]).filter((e) => {return e !== 'pano'})[0];
}

function getPanoDate(panoDate) {
  const dateSplit = panoDate.split('-');
  const date = new Date(dateSplit[0], parseInt(dateSplit[1]) - 1, 1);
  return date.toLocaleDateString('en-US', { year: "numeric", month: "short"});
}

function getOtherPanosWithDates(otherPanos) {
  const key = getPanoDateKey(otherPanos);
  return otherPanos.map(el => (
    {'pano': el['pano'], 'date': el[key].toLocaleDateString('en-US', { year:"numeric", month:"short"})}
  ))
}

async function findPanorama(svService, panoRequest, coordinates) {
  const { spherical } = await google.maps.importLibrary("geometry");
  const { StreetViewStatus, StreetViewPanorama } = await google.maps.importLibrary("streetView");

  // Send a request to the panorama service
  svService.getPanorama(panoRequest, (panoData, status) => {
    if (status === StreetViewStatus.OK) 
    {
      console.debug(`Status ${status}: panorama found.`);
      console.debug(JSON.stringify(panoData, null, 2));
      
      const panoId = panoData.location.pano;
      const panoDate = getPanoDate(panoData.imageDate);
      const otherPanos = getOtherPanosWithDates(panoData.time);
      const heading = spherical.computeHeading(panoData.location.latLng, coordinates);

      const sv = new StreetViewPanorama(
        document.getElementById('streetview'),
        {
          position: coordinates,
          center: coordinates,
          zoom: 0,
          pov: {
            pitch: 0,
            heading: heading,
          },
        }
      );
      sv.setPano(panoId);
      
      // Save these in window for easy access later
      window.sv = sv;
      window.computeHeading = spherical.computeHeading;
      // Store these in the document for the client to access
      document.getElementById('initial-pano').innerText = panoId;
      document.getElementById('current-date').innerText = panoDate
      document.getElementById('other-panos').innerText = JSON.stringify(otherPanos);
    }
    else {
      const radius = panoRequest.radius
      if (radius >= 100) {
        console.log(`Status ${status}: Could not find panorama within ${radius}m! Giving up.`);
        alert('ERROR');
      }
      else {
        panoRequest.radius += 25;
        console.log(`Status ${status}: could not find panorama within ${radius}m, trying ${panoRequest.radius}m.`);
        return findPanorama(svService, panoRequest, coordinates);
      }
    }
  });
}
