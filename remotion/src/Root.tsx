import {Composition, Still} from 'remotion';
import {PdkVoting, FPS, DURATION_FRAMES, WIDTH, HEIGHT} from './Composition';
import {LogoSquare, LogoHorizontal, LogoMono} from './brand/Logo';
import {XBanner} from './brand/Banner';
import {UpdateCard} from './brand/UpdateCard';
import {CommunityCard} from './brand/CommunityCard';
import {ExplorerActivation} from './brand/ExplorerActivation';
import {ExplorerClaim} from './brand/ExplorerClaim';
import {ThreadEnd} from './brand/ThreadEnd';
import {SpaceAnnounce} from './brand/SpaceAnnounce';
import {PdkLaunchAd, AD_FPS, AD_W, AD_H, AD_DURATION} from './ads/LaunchAd';

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="PdkVoting"
        component={PdkVoting}
        durationInFrames={DURATION_FRAMES}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
      <Still
        id="LogoSquare"
        component={LogoSquare}
        width={1024}
        height={1024}
      />
      <Still
        id="LogoHorizontal"
        component={LogoHorizontal}
        width={1200}
        height={400}
      />
      <Still
        id="LogoMono"
        component={LogoMono}
        width={1024}
        height={1024}
      />
      <Still
        id="XBanner"
        component={XBanner}
        width={1500}
        height={500}
      />
      <Still
        id="UpdateCard"
        component={UpdateCard}
        width={1600}
        height={900}
      />
      <Still
        id="CommunityCard"
        component={CommunityCard}
        width={1600}
        height={900}
      />
      <Still
        id="ExplorerActivation"
        component={ExplorerActivation}
        width={1600}
        height={900}
      />
      <Still
        id="ExplorerClaim"
        component={ExplorerClaim}
        width={1600}
        height={900}
      />
      <Still
        id="ThreadEnd"
        component={ThreadEnd}
        width={1600}
        height={900}
      />
      <Still
        id="SpaceAnnounce"
        component={SpaceAnnounce}
        width={1600}
        height={900}
        defaultProps={{date: 'Wed, Jul 29', time: '12:00 UTC'}}
      />
      <Composition
        id="PdkLaunchAd"
        component={PdkLaunchAd}
        durationInFrames={AD_DURATION}
        fps={AD_FPS}
        width={AD_W}
        height={AD_H}
      />
    </>
  );
};
