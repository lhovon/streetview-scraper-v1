// Retrieve data passed to the script from the template
const mapsData = document.currentScript.dataset;

(async function initMap() {
  const { StreetViewService } = await google.maps.importLibrary("streetView");
  const svService = new StreetViewService();
  console.debug(mapsData);

  let coordinates = { 
    lat: parseFloat(mapsData.lat),
    lng: parseFloat(mapsData.lng),
  };
  window.coordinates = coordinates;

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
  svService.getPanorama(panoRequest, function(panoData, status) {
    if (status === StreetViewStatus.OK) 
    {
      console.debug(`Status ${status}: panorama found.`);
      
      const heading = spherical.computeHeading(panoData.location.latLng, coordinates);
      const panoId = panoData.location.pano;
      const panoDate = getPanoDate(panoData.imageDate);
      const otherPanos = getOtherPanosWithDates(panoData.time);

      console.debug(otherPanos);
      
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
      
      // Save a reference to the streetview for easy access
      window.sv = sv;
      // document.getElementById('first-pano-id').innerText = panoId;
      // document.getElementById('first-pano-date').innerText = panoDate;
      document.getElementById('initial-position-pano').innerText = panoId;
      document.getElementById('current-date').innerText = panoDate
      document.getElementById('other-dates').innerText = JSON.stringify(otherPanos);
    }
    else {
      var radius = panoRequest.radius
      //Handle other statuses here
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
